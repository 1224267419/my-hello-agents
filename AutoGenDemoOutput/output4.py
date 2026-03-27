import logging
import streamlit as st

from services.price_service import (
    get_bitcoin_price,
    PriceServiceError,
)
from utils.formatter import format_currency, format_percent, format_datetime_utc

# -------------------------
# Logging
# -------------------------
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

# -------------------------
# Page Config
# -------------------------
st.set_page_config(page_title="Bitcoin Price Tracker", page_icon="₿", layout="centered")

# -------------------------
# Custom Style
# -------------------------
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .sub-text {
        color: #666;
        margin-bottom: 1rem;
    }
    .note-box {
        background-color: #f6f8fa;
        padding: 0.8rem 1rem;
        border-radius: 0.5rem;
        border: 1px solid #e6e8eb;
        margin-top: 1rem;
        margin-bottom: 1rem;
        color: #444;
        font-size: 0.95rem;
    }
    .footer-text {
        color: #888;
        font-size: 0.9rem;
        margin-top: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------
# Session State Init
# -------------------------
if "btc_data" not in st.session_state:
    st.session_state.btc_data = None

if "error_message" not in st.session_state:
    st.session_state.error_message = None

if "has_loaded_once" not in st.session_state:
    st.session_state.has_loaded_once = False


# -------------------------
# Cached Loader
# -------------------------
@st.cache_data(ttl=10, show_spinner=False)
def fetch_btc_data_cached():
    """
    带 10 秒 TTL 的缓存请求。
    避免频繁点击刷新导致免费 API 被限流。
    """
    return get_bitcoin_price()


def load_data(force_refresh: bool = False):
    """
    加载数据并更新 session state。

    设计说明：
    - force_refresh=True 时清除缓存，强制拉取最新值
    - 若请求失败，为避免误导用户，将 btc_data 清空
    """
    try:
        if force_refresh:
            fetch_btc_data_cached.clear()

        with st.spinner("正在获取最新比特币价格..."):
            data = fetch_btc_data_cached()
            st.session_state.btc_data = data
            st.session_state.error_message = None
            st.session_state.has_loaded_once = True
            logger.info("Bitcoin price loaded successfully.")
    except PriceServiceError as e:
        logger.exception("Failed to fetch bitcoin price due to service error.")
        st.session_state.error_message = str(e)
        st.session_state.btc_data = None
        st.session_state.has_loaded_once = True
    except Exception as e:
        logger.exception("Unexpected error occurred while loading bitcoin price.")
        st.session_state.error_message = "应用发生未预期错误，请稍后重试。"
        st.session_state.btc_data = None
        st.session_state.has_loaded_once = True


# -------------------------
# Header
# -------------------------
st.markdown(
    '<div class="main-title">₿ Bitcoin Price Tracker</div>', unsafe_allow_html=True
)
st.markdown(
    '<div class="sub-text">实时查看比特币当前价格（USD）及 24 小时变化情况</div>',
    unsafe_allow_html=True,
)

# 说明：24h 涨跌额为估算值
st.markdown(
    """
    <div class="note-box">
    说明：<b>24h 涨跌额</b>为根据当前价格与 24h 涨跌幅推算得到的<b>估算值</b>，
    便于快速参考，不代表第三方接口直接返回的原始绝对涨跌额。
    </div>
    """,
    unsafe_allow_html=True,
)

# -------------------------
# Initial Load
# -------------------------
if not st.session_state.has_loaded_once:
    load_data(force_refresh=False)

# -------------------------
# Actions
# -------------------------
col_btn1, col_btn2 = st.columns([1, 3])
with col_btn1:
    if st.button("🔄 刷新价格", use_container_width=True):
        load_data(force_refresh=True)

# -------------------------
# Error State
# -------------------------
if st.session_state.error_message:
    st.error(f"获取数据失败：{st.session_state.error_message}")
    st.info("当前未展示旧数据，以避免误导为最新价格。请稍后重试。")

# -------------------------
# Data Display
# -------------------------
if st.session_state.btc_data:
    data = st.session_state.btc_data

    current_price = data["current_price_usd"]
    change_amount = data["change_24h_amount_estimated"]
    change_percent = data["change_24h_percent"]
    last_updated = data["last_updated"]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(label="当前价格 (USD)", value=format_currency(current_price))

    with col2:
        st.metric(label="24h 涨跌额（估算）", value=format_currency(change_amount))

    with col3:
        st.metric(label="24h 涨跌幅", value=format_percent(change_percent))

    if change_percent > 0:
        st.success("过去 24 小时内，比特币价格上涨。")
    elif change_percent < 0:
        st.error("过去 24 小时内，比特币价格下跌。")
    else:
        st.info("过去 24 小时内，比特币价格无明显变化。")

    st.markdown(
        f'<div class="footer-text">最后更新时间：{format_datetime_utc(last_updated)}</div>',
        unsafe_allow_html=True,
    )
else:
    if not st.session_state.error_message:
        st.warning("当前暂无可用数据。")
