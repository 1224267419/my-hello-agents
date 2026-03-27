import logging
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict

import requests
import streamlit as st


# =========================
# 日志配置
# =========================
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


# =========================
# 常量定义
# =========================
APP_TITLE = "₿ 比特币价格显示应用"
APP_CAPTION = "实时查看 BTC/USD 当前价格及 24 小时变化情况"
DATA_SOURCE_TEXT = "数据来源：CoinGecko API"

API_URL = "https://api.coingecko.com/api/v3/coins/markets"
REQUEST_TIMEOUT = 10
CACHE_TTL_SECONDS = 30

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "bitcoin-price-app/1.0"
}


# =========================
# 页面配置
# =========================
st.set_page_config(
    page_title="Bitcoin Price Tracker",
    page_icon="₿",
    layout="centered"
)


# =========================
# 类型定义
# =========================
class TimeInfo(TypedDict):
    text: str
    source: Literal["market", "fetched"]


class BtcData(TypedDict):
    current_price: float
    price_change_24h: float
    price_change_percentage_24h: float
    last_updated: str
    time_source: Literal["market", "fetched"]


# =========================
# 工具函数
# =========================
def format_currency(value: float) -> str:
    """格式化美元金额，负数显示为 -$123.45"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "N/A"
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def format_percentage(value: float) -> str:
    """格式化百分比"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "N/A"
    return f"{value:.2f}%"


def format_datetime_info(api_time_str: str | None) -> TimeInfo:
    """
    优先使用 API 的市场更新时间；
    若缺失或解析失败，则回退为当前 UTC 时间，并标记为获取时间。
    """
    if api_time_str and isinstance(api_time_str, str):
        try:
            parsed = datetime.fromisoformat(api_time_str.replace("Z", "+00:00"))
            return {
                "text": parsed.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "source": "market"
            }
        except ValueError:
            logger.warning("API last_updated 时间解析失败，原始值: %s", api_time_str)

    return {
        "text": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "source": "fetched"
    }


def get_trend_text(change_value: float) -> str:
    if not isinstance(change_value, (int, float)) or isinstance(change_value, bool):
        return "数据不可用"
    if change_value > 0:
        return "上涨"
    if change_value < 0:
        return "下跌"
    return "持平"


def validate_numeric_field(data: dict[str, Any], field_name: str) -> float:
    """
    校验字段：
    1. 必须存在
    2. 不能为空
    3. 不能为 bool
    4. 必须为 int/float
    """
    if field_name not in data:
        raise ValueError(f"API 返回缺少字段: {field_name}")

    value = data[field_name]

    if value is None:
        raise ValueError(f"字段为空: {field_name}")

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"字段类型异常: {field_name}")

    return float(value)


# =========================
# 数据获取
# =========================
@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def fetch_btc_data(refresh_key: int) -> BtcData:
    logger.info("开始获取 BTC 数据，refresh_key=%s", refresh_key)

    params = {
        "vs_currency": "usd",
        "ids": "bitcoin"
    }

    response = requests.get(
        API_URL,
        params=params,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list) or len(data) == 0:
        raise ValueError("API 返回空数据或格式异常")

    btc = data[0]

    current_price = validate_numeric_field(btc, "current_price")
    price_change_24h = validate_numeric_field(btc, "price_change_24h")
    price_change_percentage_24h = validate_numeric_field(btc, "price_change_percentage_24h")

    time_info = format_datetime_info(btc.get("last_updated"))

    result: BtcData = {
        "current_price": current_price,
        "price_change_24h": price_change_24h,
        "price_change_percentage_24h": price_change_percentage_24h,
        "last_updated": time_info["text"],
        "time_source": time_info["source"],
    }

    logger.info("BTC 数据获取成功")
    return result


# =========================
# 页面渲染
# =========================
def render_header() -> None:
    st.title(APP_TITLE)
    st.caption(APP_CAPTION)


def render_refresh_section() -> bool:
    col1, col2 = st.columns([1, 2])

    with col1:
        refresh_clicked = st.button("🔄 刷新价格", use_container_width=True)

    with col2:
        st.write("点击按钮手动获取最新行情数据")

    return refresh_clicked


def render_metrics(btc_data: BtcData) -> None:
    current_price = btc_data["current_price"]
    price_change_24h = btc_data["price_change_24h"]
    price_change_percentage_24h = btc_data["price_change_percentage_24h"]
    last_updated = btc_data["last_updated"]
    time_source = btc_data["time_source"]

    st.markdown("---")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("当前价格（USD）", format_currency(current_price))

    with col2:
        st.metric("24h 涨跌额", format_currency(price_change_24h))

    with col3:
        st.metric("24h 涨跌幅", format_percentage(price_change_percentage_24h))

    trend_text = get_trend_text(price_change_24h)

    if price_change_24h > 0:
        st.success(
            f"趋势：{trend_text}，过去 24 小时上涨 "
            f"{format_currency(price_change_24h)}（{format_percentage(price_change_percentage_24h)}）"
        )
    elif price_change_24h < 0:
        st.error(
            f"趋势：{trend_text}，过去 24 小时下跌 "
            f"{format_currency(abs(price_change_24h))}（{format_percentage(abs(price_change_percentage_24h))}）"
        )
    else:
        st.info("趋势：持平，过去 24 小时价格基本无明显变化")

    time_label = "市场数据更新时间" if time_source == "market" else "数据获取时间"
    st.info(f"{time_label}：{last_updated}")


def render_footer() -> None:
    st.markdown("---")
    st.caption(DATA_SOURCE_TEXT)


# =========================
# 主流程
# =========================
def main() -> None:
    render_header()

    if "refresh_key" not in st.session_state:
        st.session_state.refresh_key = 0

    refresh_clicked = render_refresh_section()

    if refresh_clicked:
        st.session_state.refresh_key += 1
        logger.info("用户触发刷新，refresh_key=%s", st.session_state.refresh_key)

    try:
        with st.spinner("正在获取最新比特币价格..."):
            btc_data = fetch_btc_data(st.session_state.refresh_key)

        render_metrics(btc_data)

    except requests.exceptions.Timeout:
        logger.exception("请求超时")
        st.error("请求超时，请检查网络连接后重试。")

    except requests.exceptions.HTTPError as e:
        status_code = getattr(e.response, "status_code", None)
        logger.exception("HTTP 请求异常，status_code=%s", status_code)

        if status_code == 429:
            st.error("请求过于频繁，已触发接口限流，请稍后再试。")
        else:
            st.error("行情接口暂时不可用，请稍后重试。")

    except requests.exceptions.ConnectionError:
        logger.exception("网络连接失败")
        st.error("网络连接失败，无法获取行情数据，请检查网络后重试。")

    except requests.exceptions.RequestException:
        logger.exception("请求异常")
        st.error("行情数据获取失败，请稍后重试。")

    except ValueError:
        logger.exception("数据校验或解析异常")
        st.error("获取到的行情数据异常，请稍后重试。")

    except Exception:
        logger.exception("发生未预期异常")
        st.error("系统发生未预期错误，请稍后重试。")

    render_footer()


if __name__ == "__main__":
    main()
