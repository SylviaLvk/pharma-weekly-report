import streamlit as st
import requests
import os
from bs4 import BeautifulSoup
import google.generativeai as genai
import time

# ================= 核心配置区域 (只改这里) =================

# ⚠️ 请将你最新的、AIza 开头的 Key 粘贴在下面引号里！
# 这把 Key 将用于【本地运行】
LOCAL_API_KEY = "" 

# ========================================================

# --- 1. 智能环境检测 (自动判断是本地还是云端) ---
try:
    # 尝试读取云端保险箱 (Streamlit Cloud)
    # 如果这行不报错，说明在云端
    my_api_key = st.secrets["GOOGLE_API_KEY"]
    is_cloud = True
    print("☁️ 检测到云端环境，使用云端 Key")
except FileNotFoundError:
    # 报错说明没找到 secrets.toml，说明在本地 Mac
    is_cloud = False
    print("💻 检测到本地环境，使用本地硬编码 Key")
    
    # 1. 使用你上面填的 Key
    my_api_key = LOCAL_API_KEY
    
    # 2. 强制开启本地代理 (修复一直转圈的问题)
    proxy = "http://127.0.0.1:1082"
    os.environ["HTTP_PROXY"] = proxy
    os.environ["HTTPS_PROXY"] = proxy

# --- 2. 密码保护 (仅在云端生效，本地免密) ---
def check_password():
    # 如果是本地，或者云端没设密码，直接放行
    if not is_cloud:
        return True
    
    if "APP_PASSWORD" not in st.secrets:
        return True

    def password_entered():
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    st.text_input("🔒 请输入访问密码", type="password", on_change=password_entered, key="password")
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("❌ 密码错误")
    return False

# 执行密码检查
if not check_password():
    st.stop()

# --- 3. 配置 Gemini 模型 ---
try:
    genai.configure(api_key=my_api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
except Exception as e:
    st.error(f"API Key 配置出错: {e}")
    st.stop()

# --- 4. 页面主体逻辑 ---
st.set_page_config(page_title="医药行业周报生成器", page_icon="💊", layout="wide")
st.title("💊 医药行业周报 AI 生成器")

if not is_cloud:
    st.caption("🟢 当前模式：本地直连 (已启用代理 1082)")
else:
    st.caption("☁️ 当前模式：云端部署 (密码保护中)")

# 抓取函数
def get_page_content(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        
        title = soup.select_one("#activity-name")
        content = soup.select_one("#js_content")
        
        t_text = title.get_text(strip=True) if title else "无标题"
        c_text = content.get_text("\n", strip=True)[:3000] if content else "无正文"
        return f"【标题】：{t_text}\n【内容】：{c_text}\n"
    except Exception as e:
        return f"❌ 抓取失败: {e}"

# 界面布局
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. 输入链接")
    urls_input = st.text_area("请粘贴微信公众号链接（一行一个）：", height=200)
    start_btn = st.button("🚀 生成周报", type="primary")

with col2:
    st.subheader("2. 结果展示")
    result_container = st.empty()

if start_btn:
    if not urls_input.strip():
        st.warning("请先输入链接！")
    else:
        status_text = st.empty()
        bar = st.progress(0)
        all_content = ""
        url_list = [u.strip() for u in urls_input.split('\n') if u.strip()]

        for i, url in enumerate(url_list):
            status_text.text(f"正在读取第 {i+1}/{len(url_list)} 篇...")
            all_content += get_page_content(url) + "\n\n---\n\n"
            bar.progress((i + 1) / len(url_list))

        status_text.text("正在呼叫 AI 撰写报告...")
        
        try:
            prompt = f"""
            你是一位医药行业资深分析师。请根据以下抓取的文章内容，写一份周报。
            
            【内容输入】：
            {all_content}
            
            【格式要求】：
            # [大标题]
            ## 📅 导语
            ## 🚀 核心动态
            ## 💡 投资洞察
            """
            response = model.generate_content(prompt)
            bar.empty()
            status_text.empty()
            
            with col2:
                st.success("✅ 生成成功！")
                st.markdown(response.text)
        except Exception as e:
            st.error(f"生成出错: {e}")
