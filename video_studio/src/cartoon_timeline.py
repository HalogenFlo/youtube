# Chức năng: Timeline hành động, nhân vật có khớp và phong cảnh nhiều lớp.
# Lý do: Thay hình dao động lặp bằng diễn tiến hành động tất định.
# Tham khảo: https://github.com/motion-canvas/examples ; https://github.com/heygen-com/hyperframes
from __future__ import annotations
import json
import math
import re
from pathlib import Path
from PIL import Image, ImageDraw


def scene_plan(scene, scene_idx=1):
    text = ' '.join(str(scene.get(k) or '') for k in ('video_prompt', 'visual_prompt', 'narration')).lower()
    setting = next((name for name, words in (
        ('forest', ('forest', 'rừng', 'tree', 'cây', 'đom đóm')),
        ('city', ('city', 'street', 'phố', 'nhà', 'shop')),
        ('lab', ('lab', 'phòng thí nghiệm', 'enzyme', 'molecule')),
        ('space', ('space', 'planet', 'vũ trụ', 'hành tinh')),
        ('coast', ('sea', 'ocean', 'biển', 'beach')),
    ) if any(w in text for w in words)), 'meadow')
    action = next((name for name, words in (
        ('think', ('think', 'suy nghĩ', 'ngẫm')),
        ('raiseL', ('raise left', 'giơ tay trái')),
        ('raiseR', ('raise right', 'giơ tay phải')),
        ('pick', ('pick', 'nhặt', 'hái', 'cúi')),
        ('wave', ('wave', 'vẫy', 'chào')),
        ('run', ('run', 'chạy')),
        ('point', ('point', 'chỉ', 'explain', 'giải thích')),
    ) if any(w in text for w in words)), 'point')
    return dict(setting=setting, action=action, seed=scene_idx,
                beats=['approach', action, 'resolve'])


def smooth(v):
    v = max(0., min(1., v))
    return v * v * (3 - 2 * v)


def frame_commands(plan, t, duration, amp=0., include_actor=True, include_scenery=True):
    """Normalized 960x540 drawing commands, shared by Canvas and Python renderers."""
    p = max(0., min(1., t / max(.1, duration)))
    approach = smooth(p / .42)
    gesture = smooth((p - .42) / .18) * (1 - smooth((p - .82) / .18))
    walking = p < .42
    phase = t * (15 if plan['action'] == 'run' else 10)
    stride = math.sin(phase) * .65 if walking else 0.
    x = 170 + 330 * approach
    y = 406 - (abs(math.sin(phase)) * 7 if walking else 0.)
    bend = gesture * .7 if plan['action'] == 'pick' else 0.
    commands = []
    def ellipse(x, y, rx, ry, color):
        commands.append(['ellipse', x, y, rx, ry, color])
    def line(points, color, width):
        commands.append(['line', points, color, width])
    def poly(points, color):
        commands.append(['poly', points, color])
    def rect(x, y, w, h, color):
        poly([[x,y],[x+w,y],[x+w,y+h],[x,y+h]], color)
    night = plan['setting'] in ('space', 'lab')
    rect(0, 0, 960, 540, '#142541' if night else '#b9e4ef')
    ellipse(790, 90, 39, 39, '#fff3c4')
    for i in range(5):
        cx = (i * 237 + 35 - t * 5) % 1120 - 80
        ellipse(cx, 95 + i % 2 * 38, 65, 15, '#e9f4f3' if not night else '#243d60')
    poly([[0,330],[130,190],[310,325],[480,210],[680,330],[820,220],[960,330]], '#729fa8')
    poly([[0,360],[190,275],[400,350],[610,280],[830,355],[960,300],[960,540],[0,540]], '#619c83')
    rect(0, 400, 960, 140, '#82ac75' if not night else '#365368')
    poly([[0,500],[400,415],[960,440],[960,485],[380,443],[0,540]], '#d1b78d')
    if plan['setting'] == 'city':
        for i in range(6):
            bx, by = 40 + i * 166, 240 + i % 3 * 28
            rect(bx,by,110,160,'#b07e71')
            poly([[bx-8,by],[bx+55,by-45],[bx+118,by]], '#5c5367')
            for wx in (20,65):
                rect(bx+wx,by+30,24,36,'#fce3a7')
    elif plan['setting'] == 'lab':
        rect(620,310,220,18,'#dce9ed')
        line([[640,328],[640,410]],'#aac3d0',9)
        line([[820,328],[820,410]],'#aac3d0',9)
        for i in range(3):
            ellipse(665+i*62,290,20,22,'#75d6ca')
    elif plan['setting'] == 'space':
        for i in range(35):
            ellipse((i*173+plan['seed']*37)%960,(i*97)%300,2,2,'#ffffff')
        ellipse(700,200,65,65,'#b59cdd')
        line([[610,220],[780,180]],'#eadbaf',12)
    elif plan['setting'] == 'coast':
        rect(0,330,960,75,'#58b7ce')
        for i in range(10):
            wx=(i*113+t*17)%1000
            line([[wx,365],[wx+40,365]],'#d4f5ef',3)
    elif include_scenery:
        for i in range(7):
            tx=35+i*151
            rect(tx,285,17,122,'#755c49')
            for dx,dy,r in ((0,0,45),(-23,25,36),(25,23,38)):
                ellipse(tx+8+dx,270+dy,r,r,'#36755d' if plan['setting']=='forest' else '#61955f')
    # Destination prop changes state when picked up.
    picked = plan['action']=='pick' and p>.7
    if plan['action']=='pick' and not picked:
        ellipse(598,413,13,10,'#efaa49')
    ellipse(x,428,45,9,'#536e64')
    hip=[x,y-55]
    shoulder=[x+math.sin(bend)*65,y-125+abs(bend)*23]
    def joint(origin,length,angle):
        return [origin[0]+math.sin(angle)*length,origin[1]+math.cos(angle)*length]
    # Both legs have independently articulated knees and feet.
    for side in (-1,1):
        knee=joint(hip,35,stride*side)
        ankle=joint(knee,34,-stride*side*.7+max(0,stride*side)*.6)
        line([hip,knee,ankle],'#263c57',13)
        line([ankle,[ankle[0]+16,ankle[1]]],'#182c43',10)
    line([hip,shoulder],'#8ccfe8',38)
    for side in (-1,1):
        angle=-stride*side*.75
        if side==1:
            angle += gesture * (1.9 if plan['action'] in ('point','wave') else .9)
        elbow=joint(shoulder,33,angle)
        forearm=angle + (gesture*(.8+math.sin(t*8)*.35) if plan['action']=='wave' and side==1 else .25)
        hand=joint(elbow,31,forearm)
        if side==1 and plan['action']=='pick':
            reach=smooth((p-.42)/.24)
            hand=[hand[0]+(598-hand[0])*reach, hand[1]+((365 if picked else 413)-hand[1])*reach]
            elbow=[(shoulder[0]+hand[0])/2+12,(shoulder[1]+hand[1])/2]
        line([shoulder,elbow,hand],'#263c57',11)
        ellipse(*hand,8,8,'#f5d8af')
        if picked and side==1:
            ellipse(hand[0]+7,hand[1]-7,12,10,'#efaa49')
    hx,hy=shoulder[0],shoulder[1]-35
    ellipse(hx,hy,27,31,'#263c57')
    ellipse(hx,hy+2,24,27,'#f5d8af')
    blink=(t+plan['seed']*.3)%3.1>2.95
    for ex in (-8,9):
        ellipse(hx+ex,hy,2.5,1 if blink else 4,'#263c57')
    ellipse(hx+3,hy+15,6,max(1,amp*8),'#9a4950')
    # Foreground objects establish depth without moving the entire drawing.
    for i in range(8):
        gx=i*143+17
        line([[gx,530],[gx-8,508],[gx,522],[gx+9,502]],'#3e795e',4)
    if not include_actor:
        start=next(i for i,c in enumerate(commands) if c[0]=='ellipse' and c[-1]=='#536e64')
        commands=commands[:start]+commands[-8:]
    return commands


def viewport_commands(commands, width, height):
    if width >= height:
        return commands, 960, 540
    shadow=next((c for c in commands if c[0]=='ellipse' and c[-1]=='#536e64'),None)
    if shadow is None:
        # Background-only frames use the same portrait layout conversion.
        shadow=['ellipse',500,428,45,9,'#536e64']
    cx,cy=shadow[1],428
    actor=False
    output=[]
    for c in commands:
        if c is shadow:
            actor=True
        if c[0]=='line' and c[2]=='#3e795e':
            actor=False
        is_actor = actor or (c[0]=='ellipse' and c[-1]=='#efaa49')
        def pt(x,y):
            return [cx*.5625+(x-cx)*1.2,cy*960/540+(y-cy)*1.2] if is_actor else [x*.5625,y*960/540]
        if c[0]=='ellipse':
            sy = .5625 if c[-1]=='#fff3c4' else 960/540
            output.append(['ellipse',*pt(c[1],c[2]),c[3]*(1.2 if is_actor else .5625),c[4]*(1.2 if is_actor else sy),c[5]])
        else:
            output.append([c[0],[pt(*p) for p in c[1]],c[2],*c[3:]])
    return output,540,960


def render_image(commands, width, height):
    commands,vw,vh=viewport_commands(commands,width,height)
    image=Image.new('RGB',(vw,vh))
    draw=ImageDraw.Draw(image)
    for cmd in commands:
        if cmd[0]=='poly':
            draw.polygon([tuple(p) for p in cmd[1]],fill=cmd[2])
        elif cmd[0]=='line':
            draw.line([tuple(p) for p in cmd[1]],fill=cmd[2],width=cmd[3],joint='curve')
        else:
            _,x,y,rx,ry,color=cmd
            draw.ellipse((x-rx,y-ry,x+rx,y+ry),fill=color)
    # Fit composition by extending the sky/ground rather than cropping the actor.
    scale=min(width/vw,height/vh)
    fitted=image.resize((round(vw*scale),round(vh*scale)),Image.Resampling.LANCZOS)
    out=Image.new('RGB',(width,height),'#b9e4ef')
    out.paste(fitted,((width-fitted.width)//2,(height-fitted.height)//2))
    return out


def build_timeline_html(scene, scene_idx, duration, width, height, fps, envelope):
    plan=scene_plan(scene,scene_idx)
    asset=Path(__file__).resolve().parent.parent/'assets'/'characters'/'lumi'/'character.svg'
    lumi=asset.read_text(encoding='utf-8') if asset.exists() else None
    library_path=asset.parent.parent.parent/'scenery'/'nature'/'library.json'
    nature=None
    if library_path.exists() and plan['setting'] in ('forest','meadow','coast'):
        library=json.loads(library_path.read_text(encoding='utf-8'))
        text=' '.join(str(scene.get(k) or '') for k in ('narration','video_prompt','visual_prompt')).lower()
        aliases={'deer':['hươu'],'rabbit':['thỏ'],'fox':['cáo'],'squirrel':['sóc'],'owl':['cú mèo'],
                 'turtle':['rùa'],'duck':['vịt'],'fish':['cá'],'frog':['ếch'],'bird':['chim'],
                 'butterfly':['bướm'],'bee':['ong'],'pine':['thông'],'oak':['sồi'],'cherry':['anh đào'],
                 'palm':['cọ'],'bamboo':['tre'],'willow':['liễu']}
        defaults={'forest':['pine','oak','bamboo','bird'],'meadow':['oak','cherry','butterfly'],'coast':['palm','bird']}
        selected=set(defaults[plan['setting']]) | {key for key,words in aliases.items() if any(re.search(r'(?<!\w)'+re.escape(w)+r'(?!\w)',text) for w in [key,*words])}
        nature=dict(css=library['css'],objects=[o for o in library['objects'] if o['id'] in selected])
    frames=[frame_commands(plan,i/fps,duration,envelope[min(i,len(envelope)-1)] if envelope else 0,include_actor=not lumi,include_scenery=not nature)
            for i in range(max(1,round(duration*fps)))]
    frames=[viewport_commands(frame,width,height)[0] for frame in frames]
    vw,vh=(960,540) if width>=height else (540,960)
    runtime=Path(__file__).with_name('cartoon_timeline.js').read_text(encoding='utf-8')
    config=json.dumps(dict(width=width,height=height,vw=vw,vh=vh,fps=fps,duration=duration,plan=plan,frames=frames,lumi=lumi,envelope=envelope,nature=nature),ensure_ascii=False).replace('<','\\u003c')
    return '<!doctype html><meta charset="utf-8"><style>body{margin:0;background:#142541;display:grid;place-items:center;height:100vh}canvas{max-width:100vw;max-height:100vh}</style><canvas id="stage"></canvas><script>const CFG='+config+';'+runtime+'</script>'
