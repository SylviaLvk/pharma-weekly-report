import streamlit as st
import requests
import os
import re  # 引入正则库，用于智能拆分链接
import random # 引入随机库，用于模拟人类等待
from bs4 import BeautifulSoup
import google.generativeai as genai
import time

# ================= 核心配置区域 =================

# ⚠️ 本地运行时使用的 Key (请确保是最新的)
LOCAL_API_KEY = "" 

# ===============================================

# --- 1. 智能环境检测 & 网络配置 ---
try:
    # 尝试读取云端 Key
    my_api_key = st.secrets["GOOGLE_API_KEY"]
    is_cloud = True
    print("☁️ 检测到云端环境")
except FileNotFoundError:
    # 本地环境
    is_cloud = False
    print("💻 检测到本地环境")
    my_api_key = LOCAL_API_KEY
    
    # 强制开启本地代理 1082 (解决转圈问题)
    proxy = "http://127.0.0.1:1082"
    os.environ["HTTP_PROXY"] = proxy
    os.environ["HTTPS_PROXY"] = proxy

# --- 2. 密码保护 (仅云端生效) ---
def check_password():
    if not is_cloud: return True
    if "APP_PASSWORD" not in st.secrets: return True

    def password_entered():
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False): return True

    st.text_input("🔒 请输入访问密码", type="password", on_change=password_entered, key="password")
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("❌ 密码错误")
    return False

if not check_password(): st.stop()

# --- 3. 配置 Gemini ---
try:
    genai.configure(api_key=my_api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
except Exception as e:
    st.error(f"API Key 配置出错: {e}")
    st.stop()

# --- 4. 增强版抓取函数 (解决微信空白问题) ---
def get_page_content(url):
    try:
        # 🕵️‍♀️ 伪装成 Mac 电脑上的 Chrome 浏览器
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Referer": "https://weixin.qq.com/" # 假装是从微信跳转过来的
        }
        
        # 增加随机延时 (1-3秒)，防止被识别为机器人
        sleep_time = random.uniform(1, 3)
        time.sleep(sleep_time)
        
        resp = requests.get(url, headers=headers, timeout=15) # 超时延长到15秒
        
        # 检查是否被拦截 (微信有时返回200但也可能是验证页面)
        if "验证" in resp.text and "安全" in resp.text:
            return f"⚠️ 抓取失败 (触发微信验证): {url}\n"

        soup = BeautifulSoup(resp.text, "html.parser")
        
        # 微信公众号特有的提取规则
        title = soup.select_one("#activity-name")
        content = soup.select_one("#js_content")
        
        t_text = title.get_text(strip=True) if title else "无标题"
        
        if content:
            # 移除脚本和样式干扰
            for script in content(["script", "style"]):
                script.decompose()
            c_text = content.get_text("\n", strip=True)
            # 截取前 4000 字，避免 Token 溢出
            return f"【文章标题】：{t_text}\n【文章正文】：{c_text[:4000]}\n"
        else:
            # 如果没抓到 ID，尝试通用抓取
            return f"【文章标题】：{t_text}\n【提示】：未识别到微信正文结构，可能是已被删除或非微信链接。\n"
            
    except Exception as e:
        return f"❌ 网络请求出错: {url} | 原因: {e}\n"

# --- 5. 界面逻辑 ---
st.set_page_config(page_title="医药行业周报生成器", page_icon="💊", layout="wide")
st.title("💊 医药行业周报 AI 生成器 (增强版)")

if not is_cloud:
    st.info("💻 本地模式运行中 | ⚡️ 智能分词已启用 | 🛡️ 反爬虫伪装已启用")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. 输入链接 (智能识别)")
    # 提示用户支持混合输入
    urls_input = st.text_area(
        "请粘贴链接 (支持一行一个，或直接粘贴一大段混合文本)：", 
        height=300,
        placeholder="https://mp.weixin.qq.com/s/...\nhttps://mp.weixin.qq.com/s/..."
    )
    start_btn = st.button("🚀 开始生成周报", type="primary")

with col2:
    st.subheader("2. 运行结果")
    result_container = st.empty()

if start_btn:
    if not urls_input.strip():
        st.warning("⚠️ 没检测到内容呀，请先粘贴链接！")
    else:
        # 🧠 智能拆分逻辑：使用正则提取所有 http/https 开头的链接
        # 不管你是逗号隔开、空格隔开还是粘在一起，这行代码都能把链接抠出来
        url_list = re.findall(r'https?://[^\s,;"\'，。]+', urls_input)
        
        # 去重
        url_list = list(set(url_list))
        
        if not url_list:
            st.error("❌ 看起来输入框里没有有效的 http 链接，请检查一下。")
            st.stop()

        st.toast(f"🔎 识别到 {len(url_list)} 个独立链接，开始抓取...")
        
        status_text = st.empty()
        bar = st.progress(0)
        all_content = ""
        
        # 循环抓取
        for i, url in enumerate(url_list):
            status_text.markdown(f"**正在读取第 {i+1}/{len(url_list)} 篇**\n`{url[:40]}...`")
            
            content = get_page_content(url)
            
            # 如果抓取到的内容太短（比如被拦截了），给个警告但继续
            if "抓取失败" in content:
                st.warning(f"第 {i+1} 篇被拦截或无法读取，已跳过。")
            else:
                all_content += content + "\n\n" + ("=" * 30) + "\n\n"
            
            bar.progress((i + 1) / len(url_list))

        if not all_content.strip():
            st.error("😭 所有链接都抓取失败了！可能是微信防火墙太高，建议使用 Plan B：手动复制文章内容。")
            st.stop()

        status_text.text("🧠 抓取完毕，正在唤醒 Gemini 深度思考...")
        
        try:
            # 优化后的 Prompt
            prompt = f"""
            你是一位专业的医药行业首席分析师。请仔细阅读以下抓取的多篇微信公众号文章，提炼核心信息，撰写【本周医药行业深度周报】。

            【分析要求】：
            1. **去伪存真**：忽略广告、免责声明等无关信息。
            2. **深度整合**：不要简单罗列，要把多篇文章中相关的事件串联起来分析（例如：如果有两篇文章都提到某款新药，请合并分析）。
            3. **专业口吻**：使用金融/医药行业专业术语。

            【文章输入】：
            {all_content}

            【输出格式 (Markdown)】：
            # 🏥 医药行业周报 (Generated by AI)
            > **本周摘要**：[用一段话概括本周最重大的趋势]

            ## 🚀 核心重磅 (Top Stories)
            * [事件1]：[深度解读]
            * [事件2]：[深度解读]

            ## 📈 政策与市场 (Policy & Market)
            * ...

            ## 🧬 研发前沿 (R&D)
            * ...

            ## 💡 投资启示 (Investment Insights)
            * ...
            """
            
            response = model.generate_content(prompt)
            bar.empty()
            status_text.empty()
            
            with col2:
                st.success("✅ 周报生成成功！")
                st.markdown(response.text)
                st.download_button("📥 下载周报 (Markdown)", data=response.text, file_name="weekly_report.md")
                
        except Exception as e:
            st.error(f"AI 生成阶段出错: {e}")
