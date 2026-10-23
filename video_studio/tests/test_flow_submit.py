# Chức năng: Chống bấm nhầm nút tạo bộ sưu tập và chờ prompt chưa gửi.
# Lý do: Báo lỗi người dùng về Flow composer.
from unittest.mock import MagicMock
from src.flow_browser_service import submit_flow_prompt
from src.flow_browser_service import FlowBrowserController


def setup(draft):
    page=MagicMock()
    button=MagicMock()
    page.locator.return_value.count.return_value=1
    page.locator.return_value.nth.return_value=button
    button.is_visible.return_value=True
    button.is_enabled.return_value=True
    editor=MagicMock()
    editor.evaluate.return_value=draft
    return page,editor,button


def test_submit_requires_draft_consumed():
    page,editor,button=setup('still unsent')
    ok,message=submit_flow_prompt(page,editor)
    assert not ok
    assert 'vẫn còn' in message
    button.click.assert_called_once_with(timeout=5000)
    editor.press.assert_not_called()


def test_composer_submit_success():
    page,editor,button=setup('')
    assert submit_flow_prompt(page,editor)[0]
    selectors=[c.args[0] for c in page.locator.call_args_list]
    assert all("type='submit'" in selector for selector in selectors)


def test_disabled_submit_does_not_click_anything():
    page,editor,button=setup('draft')
    button.is_enabled.return_value=False
    assert not submit_flow_prompt(page,editor)[0]
    button.click.assert_not_called()
    editor.press.assert_not_called()


def test_dashboard_never_creates_project_or_collection():
    controller=object.__new__(FlowBrowserController)
    controller.page=MagicMock()
    controller.page.url='https://flow.google.com/'
    controller.cfg={}
    ok,message=controller._open_or_create_project()
    assert not ok
    controller.page.get_by_text.assert_not_called()
    controller.page.locator.assert_not_called()
    controller.page.get_by_role.assert_not_called()
    controller.page.goto.assert_not_called()


def test_saved_project_reopens_without_clicking_create():
    controller=object.__new__(FlowBrowserController)
    controller.page=MagicMock()
    controller.page.url='https://flow.google.com/'
    controller.cfg={'project_url':'https://flow.google.com/project/existing'}
    def navigate(url,**kwargs):
        controller.page.url=url
    controller.page.goto.side_effect=navigate
    assert controller._open_or_create_project()[0]
    controller.page.get_by_text.assert_not_called()
    controller.page.locator.assert_not_called()
