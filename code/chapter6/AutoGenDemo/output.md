### P2（可选优化）
1. 自动刷新开关（例如每 30 秒）
2. 数据源切换/备用源
3. 更精细的错误分类与重试机制

---

3. 更精细的错误分类与重试机制

---

## 5. 验收标准定义

### 功能验收
1. 打开页面后，能在 3 秒内看到加载提示，成功后显示：
   - 当前 BTC 价格（USD，带货币格式）
   - 24h 涨跌额（USD，正负号正确）
   - 24h 涨跌幅（百分比，正负号正确）
2. 点击“刷新”：
## 5. 验收标准定义

### 功能验收
1. 打开页面后，能在 3 秒内看到加载提示，成功后显示：
   - 当前 BTC 价格（USD，带货币格式）
   - 24h 涨跌额（USD，正负号正确）
   - 24h 涨跌幅（百分比，正负号正确）
2. 点击“刷新”：
2. 点击“刷新”：
   - 页面数据会重新请求并更新（可通过更新时间变化验证）        
   - 页面数据会重新请求并更新（可通过更新时间变化验证）        
3. 趋势图（若纳入交付）：
   - 显示过去 24 小时价格曲线
   - 数据为空/失败时，提示“趋势数据暂不可用”，不影响其他区域   

   - 显示过去 24 小时价格曲线
   - 数据为空/失败时，提示“趋势数据暂不可用”，不影响其他区域   

   - 数据为空/失败时，提示“趋势数据暂不可用”，不影响其他区域   

### 异常与体验验收
1. API 不可用/超时：
   - 页面不崩溃
   - 显示明确错误信息与重试建议
2. 限流（429）或频繁刷新：
1. API 不可用/超时：
   - 页面不崩溃
   - 显示明确错误信息与重试建议
2. 限流（429）或频繁刷新：
   - 页面不崩溃
   - 显示明确错误信息与重试建议
2. 限流（429）或频繁刷新：
2. 限流（429）或频繁刷新：
   - 有友好提示（例如“请求过于频繁，请稍后再试”）
3. UI 简洁：
   - 核心数据在首屏可见，布局不拥挤，数值可读性强

---

### 协作分工建议（便于团队并行）
- 工程 A：数据层封装（API 调用、字段解析、错误处理、缓存策略） 
- 工程 B：Streamlit UI（metrics + 图表 + 刷新交互 + 加载态）   
- 我（产品）：提供字段映射说明、验收用例清单、边界条件确认与联 调验收

请工程师开始实现
---------- TextMessage (Engineer) ----------
下面按“团队协作”的方式给出落地实现（数据层 + UI 层 + 异常/缓存 策略），并提供一份**完整可运行**的 Streamlit 代码（`app.py`）。

---

## 协作实现方案（从分析到落地）

### 工程 A（数据层）
- 选用 **CoinGecko 公共 API**（免 key，适合快速交付）
  - 当前价 + 24h 涨跌额/幅：`/api/v3/coins/markets`
  - 24h 价格序列：`/api/v3/coins/bitcoin/market_chart`
- 封装统一请求函数：
  - 超时（5s）
  - HTTP 状态码处理（尤其 429）
  - JSON 解析异常处理
- 用 `st.cache_data(ttl=20)` 做短缓存，减少频繁请求；“刷新”通过参数打破缓存。

### 工程 B（UI 层）
- Streamlit 页面结构：
  - 标题/来源说明
  - KPI：当前价、24h 涨跌额、24h 涨跌幅（`st.metric`）
  - 24h 趋势折线图（Altair）
  - 刷新按钮 + 最后更新时间
- 加载态：`st.spinner`

### 联调与降级
- 若趋势数据失败：不影响 KPI 展示，图表区域提示“暂不可用”      
- API 异常：给出明确错误 + 引导重试

---

## 运行方式

1. 保存为 `app.py`
2. 安装依赖：
   ```bash
   pip install streamlit requests pandas altair
   ```
3. 启动：
   ```bash
   streamlit run app.py
   ```

---

## 完整代码（app.py）

```python
import time
from datetime import datetime, timezone

import altair as alt
import pandas as pd
import requests
import streamlit as st


# -----------------------------
# 工程 A：数据层（API + 错误处理 + 缓存）
# -----------------------------
COINGECKO_BASE = "https://api.coingecko.com/api/v3"


class APIError(Exception):
    """统一封装 API 层错误，便于 UI 层友好展示。"""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _request_json(url: str, params: dict | None = None, timeout: float = 5.0) -> dict | list:
    """统一请求封装：超时/限流/非 200/JSON 解析错误等。"""     
    try:
        resp = requests.get(url, params=params, timeout=timeout, headers={"Accept": "application/json"})
    except requests.RequestException as e:
        raise APIError(f"网络请求失败：{e}") from e

    if resp.status_code == 429:
        raise APIError("请求过于频繁（HTTP 429），请稍后再试。", status_code=429)
    if resp.status_code >= 400:
        # 尽量带上响应文本，方便定位
        text = resp.text[:300] if resp.text else ""
        raise APIError(f"API 请求失败（HTTP {resp.status_code} ）。{text}", status_code=resp.status_code)

    try:
        return resp.json()
    except ValueError as e:
        raise APIError("API 返回不是有效 JSON，可能是服务异常或被拦截。") from e


@st.cache_data(ttl=20, show_spinner=False)
def fetch_btc_market(_cache_buster: int) -> dict:
    """
    获取 BTC 市场数据：当前价、24h 涨跌额、24h 涨跌幅等。      
    使用 _cache_buster 打破缓存以实现“刷新必更新”。
    """
    url = f"{COINGECKO_BASE}/coins/markets"
    params = {
        "vs_currency": "usd",
        "ids": "bitcoin",
        "price_change_percentage": "24h",
    }
    data = _request_json(url, params=params)

    if not isinstance(data, list) or not data:
        raise APIError("市场数据为空或结构异常。")

    item = data[0]
    # 关键字段容错读取
    try:
        current_price = float(item["current_price"])
        change_24h = float(item.get("price_change_24h", 0.0))  
        change_pct_24h = float(item.get("price_change_percentage_24h", 0.0))
    except (KeyError, TypeError, ValueError) as e:
        raise APIError("市场数据字段解析失败（可能是接口结构变 化）。") from e

    return {
        "current_price": current_price,
        "change_24h": change_24h,
        "change_pct_24h": change_pct_24h,
        "source": "CoinGecko",
        "fetched_at": datetime.now(timezone.utc),
    }


@st.cache_data(ttl=60, show_spinner=False)
def fetch_btc_chart_24h(_cache_buster: int) -> pd.DataFrame:   
    """
    获取过去 24 小时价格序列，用于趋势图。
    ttl 可稍长一些；仍支持通过 _cache_buster 强制刷新。        
    """
    url = f"{COINGECKO_BASE}/coins/bitcoin/market_chart"       
    params = {"vs_currency": "usd", "days": 1}
    data = _request_json(url, params=params)

    prices = data.get("prices")
    if not prices or not isinstance(prices, list):
        raise APIError("趋势数据为空或结构异常。")

    # prices: [[timestamp_ms, price], ...]
    df = pd.DataFrame(prices, columns=["ts_ms", "price_usd"])  
    df["time"] = pd.to_datetime(df["ts_ms"], unit="ms", utc=True).dt.tz_convert(None)  # 转成本地无 tz 展示更直观
    df = df[["time", "price_usd"]].dropna()

    if df.empty:
        raise APIError("趋势数据解析后为空。")

    return df


# -----------------------------
# 工程 B：UI 层（布局 + 展示 + 降级）
# -----------------------------
def fmt_usd(x: float) -> str:
    return f"${x:,.2f}"


def fmt_usd_signed(x: float) -> str:
    sign = "+" if x > 0 else ""
    return f"{sign}${x:,.2f}"


def fmt_pct_signed(x: float) -> str:
    sign = "+" if x > 0 else ""
    return f"{sign}{x:.2f}%"


def build_chart(df: pd.DataFrame) -> alt.Chart:
    base = alt.Chart(df).mark_line().encode(
        x=alt.X("time:T", title="Time (last 24h)"),
        y=alt.Y("price_usd:Q", title="BTC Price (USD)"),       
        tooltip=[
            alt.Tooltip("time:T", title="Time"),
            alt.Tooltip("price_usd:Q", title="Price (USD)", format=",.2f"),
        ],
    )
    return base.properties(height=320).interactive()


def main():
    st.set_page_config(page_title="BTC Price (USD)", layout="centered")

    st.title("Bitcoin Price Tracker")
    st.caption("数据来源：CoinGecko（免费公共 API）。显示 BTC/USD 当前价格与过去 24h 变化。")

    # 刷新控制：通过 session_state 传入 cache buster
    if "cache_buster" not in st.session_state:
        st.session_state.cache_buster = int(time.time())       

    col_a, col_b = st.columns([1, 1], vertical_alignment="center")
    with col_a:
        if st.button("刷新价格", type="primary", use_container_width=True):
            st.session_state.cache_buster = int(time.time())   
    with col_b:
        st.write("")  # 占位让布局更均衡
        st.write("")

    cache_buster = st.session_state.cache_buster

    # 拉取并展示 KPI
    market = None
    with st.spinner("正在加载 BTC 市场数据..."):
        try:
            market = fetch_btc_market(cache_buster)
        except APIError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"发生未知错误：{e}")

    if not market:
        st.info("请点击“刷新价格”重试。")
        return

    current_price = market["current_price"]
    change_24h = market["change_24h"]
    change_pct_24h = market["change_pct_24h"]
    fetched_at = market["fetched_at"]

    # KPI 展示
    k1, k2, k3 = st.columns(3)
    k1.metric("当前价格（USD）", fmt_usd(current_price))       
    k2.metric("24h 涨跌额", fmt_usd_signed(change_24h), delta=fmt_usd_signed(change_24h))
    k3.metric("24h 涨跌幅", fmt_pct_signed(change_pct_24h), delta=fmt_pct_signed(change_pct_24h))

    st.caption(f"最后更新时间（UTC）：{fetched_at.strftime('%Y-%m-%d %H:%M:%S')}")

    st.divider()

    # 趋势图：失败可降级
    st.subheader("过去 24 小时价格趋势")
    with st.spinner("正在加载趋势数据..."):
        try:
            df = fetch_btc_chart_24h(cache_buster)
            chart = build_chart(df)
            st.altair_chart(chart, use_container_width=True)   
        except APIError as e:
            st.warning(f"趋势数据暂不可用：{e}")
        except Exception as e:
            st.warning(f"趋势图发生未知错误：{e}")

    with st.expander("说明 / 设计要点"):
        st.write(
            "- 使用 `st.cache_data` 做短缓存，降低频繁刷新带来 的限流风险；点击“刷新价格”会通过参数打破缓存。\n"
            "- 对 HTTP 429（限流）、网络超时、JSON 解析异常做了明确提示。\n"
            "- 趋势图失败时不影响 KPI 展示，避免“白屏”。"      
        )


if __name__ == "__main__":
    main()
```

请代码审查员检查





            "- 使用 `st.cache_data` 做短缓存，降低频繁刷新带来 的限流风险；点击“刷新价格”会通过参数打破缓存。\n"
            "- 对 HTTP 429（限流）、网络超时、JSON 解析异常做了明确提示。\n"
            "- 趋势图失败时不影响 KPI 展示，避免“白屏”。"      
        )


if __name__ == "__main__":
    main()
```

请代码审查员检查





            "- 使用 `st.cache_data` 做短缓存，降低频繁刷新带来 的限流风险；点击“刷新价格”会通过参数打破缓存。\n"
            "- 对 HTTP 429（限流）、网络超时、JSON 解析异常做了明确提示。\n"
            "- 趋势图失败时不影响 KPI 展示，避免“白屏”。"      
        )


if __name__ == "__main__":
    main()
```

请代码审查员检查
            "- 使用 `st.cache_data` 做短缓存，降低频繁刷新带来 的限流风险；点击“刷新价格”会通过参数打破缓存。\n"
            "- 对 HTTP 429（限流）、网络超时、JSON 解析异常做了明确提示。\n"
            "- 趋势图失败时不影响 KPI 展示，避免“白屏”。"      
        )


if __name__ == "__main__":
            "- 使用 `st.cache_data` 做短缓存，降低频繁刷新带来 的限流风险；点击“刷新价格”会通过参数打破缓存。\n"
            "- 对 HTTP 429（限流）、网络超时、JSON 解析异常做了明确提示。\n"
            "- 趋势图失败时不影响 KPI 展示，避免“白屏”。"      
        )
            "- 使用 `st.cache_data` 做短缓存，降低频繁刷新带来 的限流风险；点击“刷新价格”会通过参数打破缓存。\n"
            "- 对 HTTP 429（限流）、网络超时、JSON 解析异常做了明确提示。\n"
            "- 使用 `st.cache_data` 做短缓存，降低频繁刷新带来 的限流风险；点击“刷新价格”会通过参数打破缓存。\n"
            "- 使用 `st.cache_data` 做短缓存，降低频繁刷新带来             "- 使用 `st.cache_data` 做短缓存，降低频繁刷新带来 的限流风险；点击“刷新价格”会通过参数打破缓存。\n"
            "- 对 HTTP 429（限流）、网络超时、JSON 解析异常做了明确提示。\n"
            "- 趋势图失败时不影响 KPI 展示，避免“白屏”。"      
        )


if __name__ == "__main__":
    main()
```

请代码审查员检查
---------- TextMessage (CodeReviewer) ----------
Enter your response: 下面是对你们提供的 `app.py` 的代码审查意见（按：代码质量 / 安全性 / 最佳实践 / 错误处理 维度），并给出可 直接落地的修改建议与关键代码片段。

---

## 总体评价
- 结构清晰：数据层（请求封装 + cache）与 UI 层分离得当，便于维 护。
- 错误处理覆盖面不错：网络异常、HTTP 状态码、JSON 解析都有兜底 ，趋势图也做了降级。
- UI 达到需求：KPI + 趋势图 + 刷新按钮 + 加载态，符合验收标准。

但存在一个**会导致“刷新按钮基本无效”的关键缓存问题**，需要优先 修复。

---

## P0（必须修复）：缓存刷新逻辑实际无效
### 问题
你们通过 `_cache_buster` 参数来“打破缓存”，但 **Streamlit 的缓 存机制会忽略以下划线开头的参数**（这正是 Streamlit 用来标记“不 要参与缓存 key”的约定），因此：

- `_cache_buster` **不会参与 cache key**
- 点击“刷新价格”后即使更新了 `_cache_buster`，缓存仍可能命中   
- 结果：刷新不一定真的重新请求 API（尤其在 TTL 内）

### 修复建议
把 `_cache_buster` 改为不以下划线开头，例如 `cache_buster`。   

**修改示例：**
```python
@st.cache_data(ttl=20, show_spinner=False)
def fetch_btc_market(cache_buster: int) -> dict:
    ...
```

```python
@st.cache_data(ttl=60, show_spinner=False)
def fetch_btc_chart_24h(cache_buster: int) -> pd.DataFrame:    
    ...
```

并相应更新调用处：
```python
market = fetch_btc_market(cache_buster)
df = fetch_btc_chart_24h(cache_buster)
```

---

## P0（建议修复）：刷新值可能在同一秒内不变
### 问题
`int(time.time())` 精度是秒。如果用户连续快速点击两次刷新（同一秒），`cache_buster` 不变，仍可能命中缓存。

### 修复建议
使用纳秒或自增计数器更稳：

**方案 A：time.time_ns()**
```python
st.session_state.cache_buster = time.time_ns()
```

**方案 B：自增**
```python
st.session_state.cache_buster = st.session_state.get("cache_buster", 0) + 1
```

---

## 代码质量 / UI 表达：`st.metric` 的 delta 使用方式不合理     
### 问题
当前写法：
```python
k2.metric("24h 涨跌额", fmt_usd_signed(change_24h), delta=fmt_usd_signed(change_24h))
k3.metric("24h 涨跌幅", fmt_pct_signed(change_pct_24h), delta=fmt_pct_signed(change_pct_24h))
```
这会导致“值”和“delta”重复展示（观感上像展示了两遍同一件事），且 `st.metric` 的 delta 本质更适合表达“相对于某个基准的变化”。   

### 建议改法（更符合常见行情卡片）
- 在“当前价格”上使用 delta（变化额或变化百分比二选一/都展示可用两列）
- “24h 涨跌额/涨跌幅”单独作为 value 展示即可（不用 delta）     

例如：
```python
k1, k2, k3 = st.columns(3)
k1.metric("当前价格（USD）", fmt_usd(current_price), delta=fmt_usd_signed(change_24h))
k2.metric("24h 涨跌额", fmt_usd_signed(change_24h))
k3.metric("24h 涨跌幅", fmt_pct_signed(change_pct_24h))        
```

---

## 最佳实践：类型注解可能引发 Python 版本兼容问题
### 问题
你们使用了 `int | None` / `dict | list` 这种 PEP604 写法，需要 **Python 3.10+**。不少 Streamlit 部署环境可能仍是 3.9（取决于团队镜像/平台）。

### 建议
如果要兼容 3.9：
- 用 `Optional[int]`、`Union[dict, list]`
- 或在文件顶部加：`from __future__ import annotations`（但 `|` 仍要求 3.10，未来注解只解决前向引用，不解决运算符语法）        

推荐保守写法：
```python
from typing import Optional, Union, Any

def _request_json(...) -> Union[dict, list]:
    ...

class APIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        ...
```

---

## 错误处理与可维护性改进建议（P1）
1. **建议使用 `requests.Session()`**
   - 复用连接，性能更好，也更“规范”
   - 你们现在每次请求都新建连接，轻量应用也能用，但属于可改进点

2. **响应文本截断虽好，但建议更“安全可控”**
   - 现在 `text = resp.text[:300]` 没问题，但建议加上 `strip()`，并避免把整段 HTML/反爬页面直接塞给用户（可以只在 debug 模式显示更多信息）
   - 更用户友好的做法：用户提示简短 + expander 展示技术细节    

3. **时间显示一致性**
   - KPI 里标注 “UTC”，趋势图里把时间 `tz_convert(None)` 变成“ 无时区时间”，可能造成用户混淆（看起来像本地时间，但其实未明确）
   - 建议统一：
     - 要么全 UTC：图表保持 UTC 并标注
     - 要么全本地：KPI 文案写“本地时间”，并把 fetched_at 转本地

---

## 轻微问题（P2）
- `fmt_usd_signed` 对于 `-0.00` 的边界可能显示奇怪（很小负数四 舍五入），可考虑对 `abs(x) < 0.005` 归零。
- `build_chart` 可以加一点样式（线色、网格淡化），但不影响功能 验收。
---
2. **把刷新值改为 `time.time_ns()` 或自增**
3. **调整 `st.metric` 用法，避免 value/delta 重复**

以上三项能显著提升“刷新可靠性 + UI 表达”。

---

代码审查完成，请用户代理测试