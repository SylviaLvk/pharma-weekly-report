import streamlit as st
import requests
import os  # <--- 确保有这个 import
# --- 🌐 核心修复：给 Streamlit 装上网络导航仪 ---
# 必须显式告诉程序走你的代理端口 (你之前告诉我你的端口是 1082)
os.environ["HTTP_PROXY"] = "http://127.0.0.1:1082"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:1082"
# ----------------------------------------------
from bs4 import BeautifulSoup
import google.generativeai as genai
import time

# ================= 配置区域 (请在此处填入你的信息) =================

try:
    my_api_key = st.secrets["GOOGLE_API_KEY"]
except Exception:
    st.error("⚠️ 未检测到 Key")

# 2. 模型选择 (保持我们要的 2.5 flash)
MODEL_NAME = 'gemini-2.5-flash' 

# ===============================================================

# 配置 Gemini
try:
    genai.configure(api_key=my_api_key)
except Exception as e:
    st.error(f"API Key 配置出错，请检查是否填对: {e}")

# 页面基础设置
st.set_page_config(page_title="医药行业周报生成器", page_icon="💊", layout="wide")

def get_page_content(url):
    """抓取逻辑，与 digest_tool.py 保持完全一致"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        # 增加 10 秒超时防止卡死
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # 提取标题
        title = soup.select_one("#activity-name")
        title = title.get_text(strip=True) if title else "无标题"
        
        # 提取正文
        content_div = soup.select_one("#js_content")
        if content_div:
            text = content_div.get_text("\n", strip=True)
            return f"【标题】：{title}\n【内容】：{text[:3000]}\n" # 截取前3000字
        else:
            return f"【标题】：{title}\n（未抓取到正文，可能是非微信链接或被拦截）\n"
            
    except Exception as e:
        return f"❌ 抓取失败 {url}: {e}\n"

def generate_report_with_ai(articles_content):
    """AI 生成逻辑，使用最新的 Prompt"""
    
    prompt = f"""
    你是一位资深的医药行业分析师。请根据以下抓取的微信公众号文章内容，撰写一份专业的【本周医药行业周报】。

    【输入内容】：
    {articles_content}

    【输出格式要求】（请严格遵守 Markdown 格式）：

    # [请生成一个极具吸引力的大标题，一句话概括本周重点，例如：赛诺菲T1D新药欧盟获批，礼来减肥药审批遭延期，巨头并购活跃]

    ## 📅 本周导语
    （在此处写一段话，高度概括本周药企动态新闻的核心趋势。）

    ## 🚀 前沿动态（临床研发与市场监管）
    （请分析上述文章，将涉及新药研发、临床试验数据公布、FDA/NMPA审批、监管政策更新的内容归类到这里。每条新闻用列表形式呈现，并加粗关键词。）

    ## 💰 资本战略（企业战略与资本交易）
    （请分析上述文章，将涉及企业并购、投融资、战略合作、人事变动、财报发布的内容归类到这里。每条新闻用列表形式呈现，并加粗关键词。）

    ## 📝 结语
    （在此处写一段结束语。要求：理性、客观、冷静，不带有任何情绪化或评判色彩，仅对行业趋势做客观陈述。）
    """
    
    model = genai.GenerativeModel(MODEL_NAME)
    response = model.generate_content(prompt)
    return response.text

# ================= 网页界面 (UI) 部分 =================

st.title("💊 医药行业周报 AI 生成器")
st.markdown("不用再改代码文件，直接粘贴链接，一键生成报告。")

# 创建两列布局
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. 输入文章链接")
    # 这里的输入框代替了 urls.txt
    urls_input = st.text_area("请把微信公众号链接粘贴在这里（一行一个）：", height=300, placeholder="https://mp.weixin.qq.com/s/...\nhttps://mp.weixin.qq.com/s/...")
    
    start_btn = st.button("🚀 开始生成周报", type="primary")

with col2:
    st.subheader("2. 生成结果")
    # 创建一个空的容器，用来放结果
    result_container = st.empty()

# ================= 核心运行逻辑 =================

if start_btn:
    if not my_api_key or "AIza" not in my_api_key:
        st.error("⚠️ 请先在 app.py 代码第 12 行填入正确的 API Key！")
    elif not urls_input.strip():
        st.warning("⚠️ 请先粘贴至少一个链接！")
    else:
        # 1. 整理链接
        url_list = [line.strip() for line in urls_input.split('\n') if line.strip()]
        st.toast(f"检测到 {len(url_list)} 个链接，准备开始工作...")
        
        # 2. 进度条
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        all_content = ""
        
        # 3. 循环抓取
        for i, url in enumerate(url_list):
            status_text.text(f"正在读取第 {i+1} 篇文章：{url[:30]}...")
            content = get_page_content(url)
            all_content += content + "\n\n" + ("-" * 20) + "\n\n"
            # 更新进度条
            progress_bar.progress((i + 1) / len(url_list))
            time.sleep(0.5) # 稍微歇一下防止封IP

        status_text.text("✅ 文章抓取完毕，正在呼叫 AI 进行深度分析（请稍等 10-20 秒）...")
        
        # 4. AI 生成
        try:
            report = generate_report_with_ai(all_content)
            
            # 5. 展示结果
            status_text.empty() # 清空状态文字
            progress_bar.empty() # 清空进度条
            
            with col2:
                st.success("生成成功！")
                st.markdown(report) # 在网页直接渲染 Markdown
                
                # 提供下载按钮
                st.download_button(
                    label="📥 下载 Markdown 文件 (可直接导入 mdnice)",
                    data=report,
                    file_name="report.md",
                    mime="text/markdown"
                )
                
        except Exception as e:
            st.error(f"AI 生成过程中出错: {e}")
