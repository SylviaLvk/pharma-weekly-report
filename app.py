import streamlit as st
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import time

# --- 🔒 密码保护门禁代码开始 ---
def check_password():
    """检查密码是否正确"""
    # 如果 Secrets 里没配密码，为了防止报错，默认允许访问
    if "APP_PASSWORD" not in st.secrets:
        return True

    def password_entered():
        """验证密码的回调函数"""
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # 验证通过后清除密码
        else:
            st.session_state["password_correct"] = False

    # 如果已经验证通过，直接返回 True
    if st.session_state.get("password_correct", False):
        return True

    # 如果没通过，显示输入框
    st.text_input(
        "🔒 请输入访问密码", 
        type="password", 
        on_change=password_entered, 
        key="password"
    )
    
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("❌ 密码错误，请重试")
        
    return False

# ⛔️ 如果没通过密码验证，直接停止运行下面的代码
if not check_password():
    st.stop()
# --- 🔒 密码保护门禁代码结束 ---


# ================= 配置区域 =================

# 1. 从云端保险箱读取 API Key (不要直接填在这里！)
try:
    my_api_key = st.secrets[""]
except Exception:
    st.error("⚠️ 未检测到 API Key，请检查 Streamlit Secrets 设置。")
    st.stop()

# 2. 模型选择
MODEL_NAME = 'gemini-2.5-flash' 

# ===========================================

# 配置 Gemini
try:
    genai.configure(api_key=my_api_key)
except Exception as e:
    st.error(f"API Key 配置出错: {e}")

# 页面基础设置
st.set_page_config(page_title="医药行业周报生成器", page_icon="💊", layout="wide")

def get_page_content(url):
    """抓取逻辑"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # 提取标题
        title = soup.select_one("#activity-name")
        title = title.get_text(strip=True) if title else "无标题"
        
        # 提取正文
        content_div = soup.select_one("#js_content")
        if content_div:
            text = content_div.get_text("\n", strip=True)
            return f"【标题】：{title}\n【内容】：{text[:3000]}\n" 
        else:
            return f"【标题】：{title}\n（未抓取到正文）\n"
            
    except Exception as e:
        return f"❌ 抓取失败 {url}: {e}\n"

def generate_report_with_ai(articles_content):
    """AI 生成逻辑"""
    prompt = f"""
    你是一位资深的医药行业分析师。请根据以下抓取的微信公众号文章内容，撰写一份专业的【本周医药行业周报】。

    【输入内容】：
    {articles_content}

    【输出格式要求】（请严格遵守 Markdown 格式）：
    # [请生成一个极具吸引力的大标题]
    ## 📅 本周导语
    ## 🚀 前沿动态
    ## 💰 资本战略
    ## 📝 结语
    """
    
    model = genai.GenerativeModel(MODEL_NAME)
    response = model.generate_content(prompt)
    return response.text

# ================= 网页界面 (UI) 部分 =================

st.title("💊 医药行业周报 AI 生成器")
st.markdown("不用再改代码文件，直接粘贴链接，一键生成报告。")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. 输入文章链接")
    urls_input = st.text_area("请把微信公众号链接粘贴在这里（一行一个）：", height=300)
    start_btn = st.button("🚀 开始生成周报", type="primary")

with col2:
    st.subheader("2. 生成结果")
    result_container = st.empty()

if start_btn:
    if not urls_input.strip():
        st.warning("⚠️ 请先粘贴至少一个链接！")
    else:
        url_list = [line.strip() for line in urls_input.split('\n') if line.strip()]
        st.toast(f"检测到 {len(url_list)} 个链接，准备开始工作...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        all_content = ""
        
        for i, url in enumerate(url_list):
            status_text.text(f"正在读取第 {i+1} 篇文章：{url[:30]}...")
            content = get_page_content(url)
            all_content += content + "\n\n" + ("-" * 20) + "\n\n"
            progress_bar.progress((i + 1) / len(url_list))
            time.sleep(0.5)

        status_text.text("✅ 抓取完毕，AI 分析中...")
        
        try:
            report = generate_report_with_ai(all_content)
            status_text.empty()
            progress_bar.empty()
            
            with col2:
                st.success("生成成功！")
                st.markdown(report)
                st.download_button("📥 下载 Markdown", data=report, file_name="report.md", mime="text/markdown")
                
        except Exception as e:
            st.error(f"AI 生成出错: {e}")
