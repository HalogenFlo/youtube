# Chức năng: Bộ kiểm thử toàn diện xác minh nâng cấp kiến trúc Xưởng Sản Xuất Video AI (video_studio v2).

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image, ImageDraw

from src import autonomous_factory as factory
from src.batch_producer import (
    invalidate_dependent_stages,
    load_job_checkpoint,
    produce_single_video_pipeline,
    save_job_checkpoint,
)
from src.policy_engine import OFFICIAL_POLICY_REGISTRY, evaluate_platform_policies
from src.production_roles import (
    PRODUCTION_ROLES_SPEC,
    build_and_validate_asset_manifest,
    get_all_role_specs,
    run_content_editor_role,
    run_director_visual_audio_planning_roles,
    run_producer_role,
    run_researcher_role,
)
from src.publishing_package_service import (
    build_platform_publishing_package,
    verify_package_ready_for_platform_publish,
)
from src.story_contract_models import (
    ContractValidationError,
    RenderManifest,
    compute_file_sha256,
    extract_and_repair_json_payload,
    validate_contract_boundary,
    validate_script_schema,
)
from src.subtitle_builder import build_ass_subtitle, build_srt_subtitle
from src.video_qa_service import run_rendered_video_qa


def _create_colorful_2d_test_image(path: str, scene_idx: int = 1, size: tuple = (1080, 1920)) -> str:
    w, h = size
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    arr[: h // 2, :, :] = [40 + (scene_idx * 35) % 160, 140, 220]
    arr[h // 2 :, :, :] = [45, 165, 75]
    arr[h // 3 : 2 * h // 3, w // 4 : 3 * w // 4, :] = [140, 207, 232]
    arr[h // 4 : h // 3, w // 3 : 2 * w // 3, :] = [250, 210, 65]

    img = Image.fromarray(arr, mode="RGB")
    draw = ImageDraw.Draw(img)
    draw.ellipse((w // 2 - 70, h // 4 - 70, w // 2 + 70, h // 4 + 70), fill=(255, 255, 255), outline=(20, 30, 50), width=6)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    img.save(path, "PNG")
    return path


class TestStudioUpgradeV2(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.work_dir = self.root / "work"
        self.out_dir = self.root / "output"
        self.state_path = self.root / "factory_state.json"
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.out_dir.mkdir(parents=True, exist_ok=True)

        self.state_patch = patch.object(factory, "STATE_PATH", self.state_path)
        self.work_patch = patch.object(factory, "FACTORY_WORK_DIR", self.work_dir)
        self.state_patch.start()
        self.work_patch.start()

    def tearDown(self):
        self.state_patch.stop()
        self.work_patch.stop()
        import gc
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_01_all_11_roles_and_malformed_llm_schema_validation(self):
        roles = get_all_role_specs()
        self.assertEqual(len(roles), 11)
        role_ids = [r["role_id"] for r in roles]
        expected_roles = [
            "producer", "researcher", "scriptwriter", "content_editor",
            "director", "visual_director", "audio_director", "video_editor",
            "fact_and_policy_officer", "independent_qa", "publishing_editor",
        ]
        self.assertEqual(role_ids, expected_roles)

        fenced_json = 'Giải thích thêm:\n```json\n{"scenes": [{"scene_num": 1, "narration": "Câu mở đầu hấp dẫn.", "video_prompt": "2D cartoon scene",},]}\n```'
        ok_rep, parsed, _ = extract_and_repair_json_payload(fenced_json)
        self.assertTrue(ok_rep)
        ok_sc, scenes, errs = validate_script_schema(parsed, content_mode="knowledge")
        self.assertTrue(ok_sc, f"Schema hợp lệ nhưng báo lỗi: {errs}")
        self.assertEqual(len(scenes), 1)
        self.assertEqual(scenes[0]["scene_id"], "sc_001")

        bad_payload = '{"scenes": [{"scene_num": 1, "narration": "", "video_prompt": ""}]}'
        ok_bad, _, bad_errs = validate_script_schema(bad_payload, content_mode="knowledge")
        self.assertFalse(ok_bad)
        self.assertGreaterEqual(len(bad_errs), 2)

        bad_zh = {"scenes": [{"scene_num": 1, "narration_vi": "Xin chào", "chinese_text": "", "pinyin": ""}]}
        ok_zh, _, zh_errs = validate_script_schema(bad_zh, content_mode="chinese_teaching_vi")
        self.assertFalse(ok_zh)
        self.assertTrue(any("chinese_text" in e for e in zh_errs))

    def test_02_corrupt_render_and_black_video_blocked_by_qa(self):
        corrupt_mp4 = str(self.work_dir / "corrupt.mp4")
        Path(corrupt_mp4).write_bytes(b"NOT_A_VALID_MP4_CONTAINER_DATA")

        scenes = [{"scene_id": "sc_001", "scene_num": 1, "narration": "Kiểm tra lỗi giải mã video.", "audio_duration": 2.0}]
        qa_corrupt = run_rendered_video_qa(video_path=corrupt_mp4, scenes=scenes)
        self.assertFalse(qa_corrupt.passed)
        self.assertTrue(qa_corrupt.release_blocked)
        self.assertGreaterEqual(qa_corrupt.critical_count, 1)
        self.assertTrue(any(i["check_id"] == "QA_01_DECODE_STREAMS" and i["status"] == "failed" for i in qa_corrupt.issues))

        black_mp4 = str(self.work_dir / "black_video.mp4")
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "color=c=black:s=480x848:r=30:d=2.0",
                "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=44100:d=2.0",
                "-af", "volume=0.2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                black_mp4,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        img_ok = _create_colorful_2d_test_image(str(self.work_dir / "sc1.png"), 1, size=(480, 848))
        aud_ok = str(self.work_dir / "sc1.mp3")
        Path(aud_ok).write_bytes(b"DUMMY" * 300)
        scenes_black = [{
            "scene_id": "sc_001", "scene_num": 1,
            "narration": "Cảnh kiểm tra màn hình đen.",
            "audio_path": aud_ok, "image_path": img_ok, "audio_duration": 2.0,
        }]
        qa_black = run_rendered_video_qa(video_path=black_mp4, scenes=scenes_black)
        self.assertFalse(qa_black.passed)
        self.assertTrue(qa_black.release_blocked)
        self.assertTrue(any(i["check_id"] == "QA_03_BLACK_FRAMES" for i in qa_black.issues))

    def test_03_missing_audio_stream_blocked_by_qa(self):
        mute_mp4 = str(self.work_dir / "no_audio.mp4")
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "color=c=blue:s=480x848:r=30:d=2.0",
                "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                mute_mp4,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        qa_mute = run_rendered_video_qa(
            video_path=mute_mp4,
            scenes=[{"scene_id": "sc_001", "scene_num": 1, "narration": "Cảnh không có tiếng.", "audio_duration": 2.0}],
        )
        self.assertFalse(qa_mute.passed)
        self.assertTrue(qa_mute.release_blocked)
        self.assertTrue(any(i["check_id"] == "QA_01_AUDIO_STREAM" and i["severity"] == "critical" for i in qa_mute.issues))

    def test_04_subtitle_desync_overflow_and_safe_zone_violation(self):
        valid_mp4 = str(self.work_dir / "valid_2s.mp4")
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "color=c=teal:s=1080x1920:r=30:d=2.5",
                "-f", "lavfi", "-i", "sine=frequency=200:sample_rate=44100:d=2.5",
                "-af", "volume=0.2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                valid_mp4,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

        bad_ass = str(self.work_dir / "bad_subs.ass")
        Path(bad_ass).write_text(
            "[Script Info]\nPlayResX: 1080\nPlayResY: 1920\n\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Default,Montserrat,64,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,1,5,50,50,960,1\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:00.00,0:00:12.00,Default,,0,0,0,,Đây là một dòng phụ đề cực kỳ dài không được ngắt dòng khiến chữ bị tràn ra ngoài khung hình điện thoại hoàn toàn\n",
            encoding="utf-8",
        )

        img_p = _create_colorful_2d_test_image(str(self.work_dir / "s1.png"), 1)
        aud_p = str(self.work_dir / "s1.mp3")
        Path(aud_p).write_bytes(b"AUDIO" * 300)
        scenes = [{
            "scene_id": "sc_001", "scene_num": 1,
            "narration": "Đây là câu ngắn.",
            "image_path": img_p, "audio_path": aud_p, "audio_duration": 2.5,
        }]

        qa_sub = run_rendered_video_qa(video_path=valid_mp4, scenes=scenes, ass_subtitle_path=bad_ass, orientation="vertical")
        check_ids = {i["check_id"] for i in qa_sub.issues if i["status"] == "failed"}
        self.assertIn("QA_06_SUBTITLE_AUDIO_DESYNC", check_ids)
        self.assertIn("QA_07_SUBTITLE_FRAME_OVERFLOW", check_ids)
        self.assertIn("QA_07_SUBTITLE_SAFE_ZONE_VIOLATION", check_ids)

    def test_05_qa_insufficient_evidence_records_not_checked(self):
        valid_mp4 = str(self.work_dir / "check_evidence.mp4")
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "color=c=navy:s=1080x1920:r=30:d=2.0",
                "-f", "lavfi", "-i", "sine=frequency=210:sample_rate=44100:d=2.0",
                "-af", "volume=0.2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                valid_mp4,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        qa = run_rendered_video_qa(
            video_path=valid_mp4,
            scenes=[{"scene_id": "sc_001", "scene_num": 1, "narration": "Khám phá đại dương sâu thẳm.", "audio_duration": 2.0}],
            vlm_frame_evaluator=None,
        )
        vlm_issue = next((i for i in qa.issues if i["check_id"] == "QA_08_SEMANTIC_VISUAL_NARRATION_MATCH"), None)
        self.assertIsNotNone(vlm_issue)
        self.assertEqual(vlm_issue["status"], "not_checked")
        self.assertEqual(vlm_issue["confidence"], 0.0)
        self.assertGreaterEqual(qa.unchecked_count, 1)

    @patch("src.batch_producer.generate_flow_image")
    @patch("src.batch_producer.generate_script")
    def test_06_07_checkpoint_resume_and_idempotent_retry(self, mock_script, mock_flow_img):
        mock_script.return_value = (True, {
            "scenes": [
                {"scene_num": 1, "narration": "Vì sao bầu trời lại có màu xanh vào ban ngày?", "video_prompt": "2D stickman looking at blue sky"},
                {"scene_num": 2, "narration": "Chính vì ánh sáng mặt trời bị tán xạ Rayleigh trong khí quyển.", "video_prompt": "2D stickman prism light scattering"},
            ]
        })

        call_attempt = {"scene_2": 0}

        def side_effect_flow(prompt, output_path, **kwargs):
            if "scene_001" in output_path:
                _create_colorful_2d_test_image(output_path, scene_idx=1, size=(480, 848))
                return True, output_path
            call_attempt["scene_2"] += 1
            if call_attempt["scene_2"] <= 3:
                return False, "Simulated Flow disconnect on scene 2"
            _create_colorful_2d_test_image(output_path, scene_idx=2, size=(480, 848))
            return True, output_path

        mock_flow_img.side_effect = side_effect_flow

        with patch("src.batch_producer.time.sleep", return_value=None), \
             patch("src.studio_editorial_service.call_ollama", return_value=(False, "offline")):
            ok1, res1, _ = produce_single_video_pipeline(
                topic="Vì sao bầu trời màu xanh",
                video_index=1,
                batch_work_dir=str(self.work_dir),
                output_dir=str(self.out_dir),
                job_key="job_idem_01",
                studio_mode=True,
                turbo_mode=False,
            )
            self.assertFalse(ok1, "Khi cảnh 2 lỗi ở chế độ studio_mode=True, hệ thống không được âm thầm coi là thành công!")
            self.assertEqual(mock_script.call_count, 1)

            cp = load_job_checkpoint(str(self.work_dir / "job_job_idem_01"))
            self.assertIn("scripting", cp["completed_stages"])
            self.assertIn("tts", cp["completed_stages"])

            ok2, final_path_2, meta2 = produce_single_video_pipeline(
                topic="Vì sao bầu trời màu xanh",
                video_index=1,
                batch_work_dir=str(self.work_dir),
                output_dir=str(self.out_dir),
                job_key="job_idem_01",
                studio_mode=True,
                turbo_mode=False,
                resume_from_checkpoint=True,
            )
            self.assertTrue(ok2, f"Resume thất bại: {final_path_2}")
            self.assertEqual(mock_script.call_count, 1)

            ok3, final_path_3, _ = produce_single_video_pipeline(
                topic="Vì sao bầu trời màu xanh",
                video_index=1,
                batch_work_dir=str(self.work_dir),
                output_dir=str(self.out_dir),
                job_key="job_idem_01",
                studio_mode=True,
                turbo_mode=False,
                resume_from_checkpoint=True,
            )
            self.assertTrue(ok3)
            self.assertEqual(final_path_2, final_path_3)
            mp4_files = list(self.out_dir.glob("*.mp4"))
            self.assertEqual(len(mp4_files), 1, f"Retry tạo file trùng lặp: {mp4_files}")

    @patch.object(factory, "ensure_factory_worker")
    def test_08_09_10_cancel_post_approval_edit_and_ai_disclosure_publish_gate(self, mock_worker):
        ids = factory.add_factory_jobs("Khám phá sao Hỏa", count=2, language="vi")
        job_cancel_id, job_main_id = ids[0], ids[1]

        ok_cancel = factory.cancel_job(job_cancel_id, keep_cancelled_record=True)
        self.assertTrue(ok_cancel)
        st = factory.get_factory_state()
        j_can = next(j for j in st["jobs"] if j["id"] == job_cancel_id)
        self.assertEqual(j_can["status"], "cancelled")
        self.assertEqual(j_can["lifecycle_state"], "cancelled")

        dummy_mp4 = str(self.out_dir / f"video_job_{job_main_id}_v01.mp4")
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "color=c=darkslateblue:s=1080x1920:r=30:d=3.0",
                "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=44100:d=3.0",
                "-af", "volume=0.2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                dummy_mp4,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        brief = run_producer_role("Khám phá sao Hỏa", project_id=job_main_id)
        research = run_researcher_role(brief)
        s1_img = _create_colorful_2d_test_image(str(self.work_dir / "m1.png"), 1)
        s1_aud = str(self.work_dir / "m1.mp3")
        Path(s1_aud).write_bytes(b"AUD" * 400)
        scenes = [{
            "scene_id": "sc_001", "scene_num": 1,
            "narration": "Sao Hỏa có ngọn núi lửa Olympus Mons cao nhất Hệ Mặt Trời.",
            "video_prompt": "2D stickman on Mars",
            "image_path": s1_img, "audio_path": s1_aud, "audio_duration": 3.0,
        }]
        script_c = run_content_editor_role(brief, research, scenes)
        plan_c = run_director_visual_audio_planning_roles(brief, script_c)
        assets_c = build_and_validate_asset_manifest(plan_c, script_c.scenes)
        ass_p = str(self.work_dir / "m1.ass")
        srt_p = str(self.work_dir / "m1.srt")
        build_ass_subtitle([{"word": "Sao", "start": 0.0, "end": 1.0}, {"word": "Hỏa", "start": 1.0, "end": 2.8}], ass_p)
        build_srt_subtitle([{"word": "Sao", "start": 0.0, "end": 1.0}, {"word": "Hỏa", "start": 1.0, "end": 2.8}], srt_p)

        rnd_c = RenderManifest(
            render_id="rnd_mars",
            manifest_id=assets_c.manifest_id,
            video_path=dummy_mp4,
            video_sha256=compute_file_sha256(dummy_mp4),
            ass_subtitle_path=ass_p,
            srt_subtitle_path=srt_p,
            subtitle_sha256=compute_file_sha256(ass_p),
            duration_sec=3.0,
        )
        qa_c = run_rendered_video_qa(dummy_mp4, script_c.scenes, ass_subtitle_path=ass_p)
        pol_c = evaluate_platform_policies(brief, research, script_c, assets_c, 3.0, rnd_c.video_sha256)
        pkg_c = build_platform_publishing_package(
            brief, research, script_c, rnd_c, qa_c, pol_c,
            package_output_dir=str(self.out_dir / "pkg_mars"),
        )

        factory._update_job(
            job_main_id,
            status="completed",
            lifecycle_state="ready_for_review",
            output_path=dummy_mp4,
            metadata={
                "final_path": dummy_mp4,
                "scenes": script_c.scenes,
                "qa_report": qa_c.to_dict(),
                "policy_report": pol_c.to_dict(),
                "publishing_package": pkg_c.to_dict(),
                "publishing": {"title": pkg_c.youtube["recommended_title"]},
            },
        )

        ok_pub_unapproved, msg_unapproved = factory.publish_approved_job(
            job_main_id, platform="youtube", explicit_publish_permission=True
        )
        self.assertFalse(ok_pub_unapproved)
        self.assertIn("approved_by_user=False", msg_unapproved)

        ok_app, _ = factory.approve_job_for_publishing(job_main_id)
        self.assertTrue(ok_app)

        ok_no_perm, msg_no_perm = factory.publish_approved_job(
            job_main_id, platform="youtube", explicit_publish_permission=False
        )
        self.assertFalse(ok_no_perm)
        self.assertIn("explicit_publish_permission=False", msg_no_perm)

        ok_tt_pub, msg_tt_pub = factory.publish_approved_job(
            job_main_id, platform="tiktok", explicit_publish_permission=True
        )
        self.assertFalse(ok_tt_pub)
        self.assertIn("TIKTOK", msg_tt_pub.upper())
        self.assertIn("AI-generated content", msg_tt_pub)

        ok_yt_pub, _ = factory.publish_approved_job(
            job_main_id, platform="youtube", explicit_publish_permission=True
        )
        self.assertTrue(ok_yt_pub)

        ok_edit, _ = factory.update_job_metadata_or_script(
            job_main_id,
            youtube_title="Tiêu đề Sao Hỏa Đã Được Biên Tập Viên Chốt",
        )
        self.assertTrue(ok_edit)
        st_after = factory.get_factory_state()
        j_after = next(j for j in st_after["jobs"] if j["id"] == job_main_id)
        self.assertFalse(j_after.get("approved_by_user"), "Sửa nội dung sau khi duyệt phải thu hồi cờ approved_by_user!")
        self.assertEqual(j_after["lifecycle_state"], "needs_review")
        self.assertEqual(
            j_after["metadata"]["publishing"]["title"],
            "Tiêu đề Sao Hỏa Đã Được Biên Tập Viên Chốt",
        )

        cp_after = load_job_checkpoint(str(self.work_dir / f"job_{job_main_id}"))
        pkg_rebuilt = build_platform_publishing_package(
            brief, research, script_c, rnd_c, qa_c, pol_c,
            package_output_dir=str(self.out_dir / "pkg_mars"),
            existing_user_edits=cp_after.get("approved_edits", {}),
        )
        self.assertEqual(pkg_rebuilt.youtube["recommended_title"], "Tiêu đề Sao Hỏa Đã Được Biên Tập Viên Chốt")

    @patch("src.batch_producer.generate_flow_image")
    @patch("src.batch_producer.generate_script")
    def test_11_full_e2e_pipeline_with_real_ffmpeg_render_qa_and_package(self, mock_script, mock_flow_img):
        mock_script.return_value = (True, {
            "scenes": [
                {
                    "scene_num": 1,
                    "narration": "Bạn có bao giờ tự hỏi vì sao loài đom đóm lại phát sáng lung linh trong đêm tối không?",
                    "video_prompt": "2D cartoon stickman CH01 watching glowing fireflies in a dark blue forest",
                },
                {
                    "scene_num": 2,
                    "narration": "Chính vì trong bụng đom đóm diễn ra phản ứng hóa học giữa chất luciferin và oxy tạo ra ánh sáng lạnh.",
                    "video_prompt": "2D flat illustration showing glowing yellow light particles without heat",
                },
                {
                    "scene_num": 3,
                    "narration": "Nhờ đó, đom đóm phát sáng hiệu quả gần như tuyệt đối mà không hề bị bỏng. Hãy theo dõi kênh nhé!",
                    "video_prompt": "2D stickman smiling with a happy glowing firefly on finger",
                },
            ]
        })

        def fake_flow_img(prompt, output_path, **kwargs):
            sc_idx = 1 if "001" in output_path else (2 if "002" in output_path else 3)
            _create_colorful_2d_test_image(output_path, scene_idx=sc_idx, size=(1080, 1920))
            return True, output_path

        mock_flow_img.side_effect = fake_flow_img

        with patch("src.studio_editorial_service.call_ollama", return_value=(False, "offline")), \
             patch("src.llm_service.call_ollama", return_value=(False, "offline")):
            ok, final_video_path, meta = produce_single_video_pipeline(
                topic="Bí mật ánh sáng lạnh của loài đom đóm",
                video_index=1,
                batch_work_dir=str(self.work_dir),
                output_dir=str(self.out_dir),
                language="vi",
                orientation="vertical",
                image_engine="flow",
                media_mode="flow_image",
                job_key="e2e_firefly",
                studio_mode=True,
                turbo_mode=False,
            )

        self.assertTrue(ok, f"E2E pipeline thất bại: {final_video_path}")
        self.assertTrue(os.path.exists(final_video_path))
        self.assertGreater(os.path.getsize(final_video_path), 15000)

        qa_rep = meta.get("qa_report", {})
        self.assertGreaterEqual(qa_rep.get("overall_score", 0), 85.0, f"QA report: {qa_rep}")
        self.assertEqual(qa_rep.get("critical_count"), 0)
        self.assertFalse(qa_rep.get("release_blocked"))
        self.assertTrue(qa_rep.get("passed"))

        pol_rep = meta.get("policy_report", {})
        self.assertTrue(pol_rep.get("allowed_to_publish"))
        self.assertIn("youtube", pol_rep.get("platforms", {}))
        self.assertIn("tiktok", pol_rep.get("platforms", {}))

        pkg = meta.get("publishing_package", {})
        self.assertTrue(os.path.exists(pkg.get("video_path", "")))
        self.assertTrue(os.path.exists(pkg.get("ass_subtitle_path", "")))
        self.assertTrue(os.path.exists(pkg.get("srt_subtitle_path", "")))
        self.assertTrue(os.path.exists(pkg.get("qa_report_path", "")))
        self.assertTrue(os.path.exists(pkg.get("policy_report_path", "")))
        self.assertTrue(os.path.exists(pkg.get("manifest_path", "")))
        self.assertEqual(len(pkg["youtube"]["alternative_titles"]), 2)
        self.assertEqual(len(pkg["youtube"]["chapters"]), 3)
        self.assertEqual(pkg["youtube"]["chapters"][0]["timestamp"], "00:00")



    @patch("src.batch_producer.generate_script")
    def test_12_html_multi_frame_cartoon_animation_and_audible_soundtrack(self, mock_script):
        mock_script.return_value = (True, {
            "scenes": [
                {
                    "scene_num": 1,
                    "narration": "Bạn có bao giờ tự hỏi vì sao loài đom đóm lại phát sáng lung linh trong đêm tối không?",
                    "video_prompt": "2D cartoon character CH01 watching glowing fireflies in a dark blue bamboo forest",
                },
                {
                    "scene_num": 2,
                    "narration": "Trong bụng đom đóm diễn ra phản ứng giữa hợp chất luciferin và oxy tạo ra ánh sáng lạnh hiệu suất chín mươi tám phần trăm.",
                    "video_prompt": "2D science lab diagram showing glowing green luciferin particles without heat",
                },
            ]
        })
        with patch("src.studio_editorial_service.call_ollama", return_value=(False, "offline")), \
             patch("src.llm_service.call_ollama", return_value=(False, "offline")):
            ok, final_video_path, meta = produce_single_video_pipeline(
                topic="Bí mật ánh sáng lạnh của loài đom đóm",
                video_index=1,
                batch_work_dir=str(self.work_dir),
                output_dir=str(self.out_dir),
                language="vi",
                orientation="vertical",
                image_engine="cartoon_2d",
                media_mode="cartoon_2d",
                job_key="html_anim_firefly",
                studio_mode=True,
                turbo_mode=True,
                flow_workers=2,
                tts_workers=2,
            )
        self.assertTrue(ok, f"HTML Multi-Frame pipeline failed: {final_video_path}")
        self.assertTrue(os.path.exists(final_video_path))
        scenes_out = meta.get("scenes", [])
        self.assertEqual(len(scenes_out), 2)
        for sc in scenes_out:
            self.assertEqual(sc.get("asset_source"), "html_canvas_multi_frame")
            self.assertTrue(os.path.exists(sc.get("html_frame_path", "")))
            self.assertTrue(os.path.exists(sc.get("video_path", "")))
        qa_rep = meta.get("qa_report", {})
        self.assertTrue(qa_rep.get("passed"), f"QA failed: {qa_rep}")
        self.assertEqual(qa_rep.get("critical_count"), 0)

    def test_job_video_path_resolution_and_missing_job_management(self):
        """Kiểm thử tự động khôi phục đường dẫn video, dọn dẹp và chạy lại các job thiếu file."""
        fake_video_file = self.out_dir / "video_sample_test.mp4"
        fake_video_file.write_bytes(b"\x00\x00\x00\x1cftypmp42" + b"\x00" * 100)

        # 1. Test path resolution khi file tồn tại
        job_with_file = {
            "id": "job_resolved_01",
            "output_path": str(fake_video_file),
            "status": "completed",
        }
        v_path, m_path = factory.resolve_job_video_and_metadata_paths(job_with_file)
        self.assertIsNotNone(v_path)
        self.assertTrue(os.path.exists(v_path))

        # 2. Test path resolution khi đường dẫn cũ không tồn tại
        job_missing_file = {
            "id": "job_ghost_99",
            "output_path": "C:\\fake\\non_existent_dir\\video_ghost.mp4",
            "status": "completed",
        }
        v_miss, m_miss = factory.resolve_job_video_and_metadata_paths(job_missing_file)
        self.assertIsNone(v_miss)

        # 3. Test delete_job & clear_missing_video_jobs
        with factory._LOCK:
            st = factory._load_unlocked()
            st["jobs"].extend([
                {"id": "job_test_keep", "status": "completed", "output_path": str(fake_video_file)},
                {"id": "job_test_delete", "status": "completed", "output_path": "C:\\fake\\missing1.mp4"},
                {"id": "job_test_clean", "status": "completed", "output_path": "C:\\fake\\missing2.mp4"},
            ])
            factory._save_unlocked(st)

        # Xóa đơn lẻ bằng delete_job
        del_ok = factory.delete_job("job_test_delete")
        self.assertTrue(del_ok)

        # Dọn dẹp hàng loạt bằng clear_missing_video_jobs
        removed_count = factory.clear_missing_video_jobs()
        self.assertGreaterEqual(removed_count, 1)

        # Job có file thực tế vẫn còn nguyên
        state_after = factory.get_factory_state()
        self.assertTrue(any(j.get("id") == "job_test_keep" for j in state_after.get("jobs", [])))
        self.assertFalse(any(j.get("id") == "job_test_delete" for j in state_after.get("jobs", [])))
        self.assertFalse(any(j.get("id") == "job_test_clean" for j in state_after.get("jobs", [])))

        # Dọn dẹp job test
        factory.delete_job("job_test_keep")


if __name__ == "__main__":
    unittest.main()
