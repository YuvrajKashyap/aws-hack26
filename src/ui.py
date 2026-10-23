"""Shared visual language for the maintenance console; business logic stays separate."""
import streamlit as st

def console_style():
    st.markdown('''<style>
    :root{--accent:#b76438;--ink:#182b34;--muted:#637680;--paper:#f4f5f0}
    .stApp{background:var(--paper);color:var(--ink)}
    [data-testid="stHeader"]{background:rgba(244,245,240,.93)}
    .block-container{max-width:1400px;padding-top:2rem;padding-bottom:4rem}
    h1{font-family:'Segoe UI',sans-serif!important;font-size:clamp(2rem,3.4vw,3.5rem)!important;font-weight:550!important;letter-spacing:-1.8px!important;line-height:1.1!important;margin-bottom:.8rem!important}
    h2,h3{letter-spacing:-.6px!important;font-weight:550!important}
    [data-testid="stSidebar"]{background:#13232d;color:#dce5e8;border-right:1px solid #33444d}
    [data-testid="stSidebar"] a,[data-testid="stSidebar"] p,[data-testid="stSidebar"] span{color:#dce5e8!important}
    [data-testid="stSidebarNav"]{padding-top:1.5rem}
    [data-testid="stSidebarNav"] a:hover{background:#2b3d47!important}
    [data-testid="stMetric"]{border-top:2px solid #bc7249;padding:18px 16px;background:#fff;border-radius:0 0 6px 6px}
    [data-testid="stMetricValue"]{font-family:Consolas,monospace;font-size:2rem;letter-spacing:-1.5px}
    [data-testid="stMetricLabel"]{color:#60717a;font-size:12px;text-transform:uppercase;letter-spacing:1px}
    .stButton>button{border-radius:5px;min-height:44px;font-weight:600;transition:transform .22s cubic-bezier(.16,1,.3,1),box-shadow .22s,border-color .22s}
    .stButton>button:hover{transform:translateY(-2px);box-shadow:0 5px 0 #b7643822;border-color:#b76438}
    .stButton>button[kind="primary"]{background:#a6502c;border:1px solid #a6502c;color:white}
    [data-testid="stExpander"]{background:#fff;border:1px solid #d9e0de;border-radius:6px}
    [data-testid="stAlert"]{border-radius:5px;font-size:13px}
    .brand-line{font:11px Consolas,monospace;letter-spacing:2px;color:#9f532e;margin-bottom:22px;border-bottom:1px solid #d3dcda;padding-bottom:14px;display:flex;justify-content:space-between}
    .brand-line span{color:#9f532e!important}
    .intro{max-width:760px;color:#64747b;font-size:16px;line-height:1.65;margin:0 0 20px}
    .stage{display:flex;gap:0;margin:22px 0 28px;border-bottom:1px solid #d2dbd9}.stage span{padding:12px 24px 12px 0;margin-right:25px;font:11px Consolas,monospace;color:#697e87;letter-spacing:1px}.stage b{color:#a6502c;margin-right:8px}
    .empty-scene{background:#152630;color:#e9eeeb;padding:32px;border-radius:8px;min-height:140px;border-left:4px solid #bf7a4e}.empty-scene strong{font-size:24px;font-weight:500;display:block;margin-bottom:10px}.empty-scene p{color:#acbdc4;font-size:14px;margin:0}
    @media(max-width:700px){.block-container{padding:1.5rem 1rem}.stage span{padding-right:5px;margin-right:10px;font-size:9px}.brand-line{font-size:9px}h1{letter-spacing:-1px!important}}
    @media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
    </style>''',unsafe_allow_html=True)
    st.markdown('<div class="brand-line"><span>FIELDWORK / MAINTENANCE INTELLIGENCE</span><span>MANUFACTURING · TRACK 02</span></div>',unsafe_allow_html=True)

def stages():
    st.markdown('<div class="stage"><span><b>01</b> OBSERVE</span><span><b>02</b> ASSESS</span><span><b>03</b> REVIEW EVIDENCE</span><span><b>04</b> TAKE ACTION</span></div>',unsafe_allow_html=True)
