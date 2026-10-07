import os
import re
import json
import time
import requests
import datetime

# ==============================================================================
# 1. 微信全局测试号配置
# ==============================================================================
APP_ID = os.environ.get("APP_ID", "你的_appID").strip()
APP_SECRET = os.environ.get("APP_SECRET", "你的_appSecret").strip()
TEMPLATE_ID = os.environ.get("TEMPLATE_ID", "你的_模板ID").strip()


# ==============================================================================
# 2. 🎮 从 GitHub Secrets 动态读取并解析多账号配置
# ==============================================================================
# 配置格式说明：
# ACCOUNTS_JSON 应为以下 JSON 数组格式：
# [
#   {
#     "name": "游戏角色昵称1",
#     "open_id": "微信推送接收者的openid",
#     "cookie": "从抓包工具获取的完整 Cookie 字符串（包含 ct, userId, openid, access_token 等）",
#     "fav_set": ["离谱子", "掠夺狂潮 暴徒"]
#   }
# ]
accounts_json_raw = os.environ.get("ACCOUNTS_JSON", "[]")

try:
    ACCOUNTS = json.loads(accounts_json_raw)
    # 将 JSON 数组中的关注列表转换为 set 集合类型，方便高效查询
    for acc in ACCOUNTS:
        if "fav_set" in acc:
            acc["fav_set"] = set(acc["fav_set"])
except Exception as e:
    print(f"❌ 解析环境变量 ACCOUNTS_JSON 失败，请检查 Secret 格式是否正确: {e}")
    ACCOUNTS = []


# ==============================================================================
# 3. 腾讯 API 与持久化配置（核心新增）
# ==============================================================================
API_BASE = "https://app.mval.qq.com"
COMMON_PARAMS = "source_game_zone=agame&game_zone=agame"

# 持久化凭证保存目录
CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")

# 品质颜色映射
QUALITY_COLORS = {
    "orange": "#FF8C00",  # 金色 - 至臻/独占
    "purple": "#8E44AD",  # 紫色 - 尊享
    "blue": "#2980B9",    # 蓝色 - 卓越
    "green": "#27AE60",   # 绿色 - 精选
    "normal": "#333333"
}
COLOR_WISH = "#FF4655"    # 瓦罗兰特红 - 心愿命中高亮


def get_safe_filename(name: str) -> str:
    """过滤账号名称中的非法字符，生成安全的文件名"""
    return re.sub(r'[\\/*?:"<>| ]', "_", name)


def parse_cookie(cookie_str: str) -> dict:
    """解析 cookie 字符串为字典"""
    cookie_dict = {}
    if not cookie_str:
        return cookie_dict
    for item in cookie_str.split(";"):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            cookie_dict[k.strip()] = v.strip()
    return cookie_dict


# ==============================================================================
# 4. Token 读写与 Session 管理（核心新增）
# ==============================================================================
def load_persisted_token(acc_name: str, token_type: str, default_val: str) -> str:
    """从本地读取持久化的 ct 或 access_token"""
    safe_name = get_safe_filename(acc_name)
    file_path = os.path.join(CONFIG_DIR, f".valorant_{safe_name}_{token_type}")
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                val = f.read().strip()
                if val:
                    return val
        except Exception as e:
            print(f"⚠️ 读取 {token_type} 缓存失败: {e}")
    return default_val


def save_persisted_token(acc_name: str, token_type: str, val: str):
    """保存 ct 或 access_token 到本地"""
    if not val:
        return
    os.makedirs(CONFIG_DIR, exist_ok=True)
    safe_name = get_safe_filename(acc_name)
    file_path = os.path.join(CONFIG_DIR, f".valorant_{safe_name}_{token_type}")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(val)
    except Exception as e:
        print(f"⚠️ 保存 {token_type} 缓存失败: {e}")


def create_session(acc_name: str, raw_cookie_str: str) -> requests.Session:
    """创建并配置 Session，优先加载本地持久化的 access_token"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "mval/2.6.0.10062 Channel/5 Mozilla/5.0 (Linux; Android 16; wv) AppleWebKit/537.36",
        "Accept-Encoding": "gzip",
        "Content-Type": "application/json; charset=utf-8",
    })
    cookie_dict = parse_cookie(raw_cookie_str)
    
    # ct 不需要放到标准的 session.cookies 中
    cookie_dict.pop("ct", None)
    
    # 优先载入本地持久化的最新的 access_token
    persisted_at = load_persisted_token(acc_name, "at", cookie_dict.get("access_token", ""))
    if persisted_at:
        cookie_dict["access_token"] = persisted_at

    requests.utils.add_dict_to_cookiejar(session.cookies, cookie_dict)
    return session


def api_post(session: requests.Session, path: str, body: dict = None) -> dict:
    """向腾讯掌瓦发送 POST 请求"""
    url = f"{API_BASE}{path}?{COMMON_PARAMS}"
    try:
        resp = session.post(url, json=body or {}, timeout=15)
        try:
            return resp.json()
        except json.JSONDecodeError:
            # 解决腾讯服务端偶发返回重复 JSON 导致解析失败的 Bug
            text = resp.text.strip()
            decoder = json.JSONDecoder()
            obj, _ = decoder.raw_decode(text)
            return obj
    except Exception as e:
        print(f"❌ API 请求异常 [{path}]: {e}")
        return {}


# ==============================================================================
# 5. Token 双重自动刷新（核心移植）
# ==============================================================================
def refresh_token(session: requests.Session, acc_name: str) -> str:
    """刷新并保存 access_token"""
    cookie = {c.name: c.value for c in session.cookies}
    body = {
        "type": cookie.get("acctype", "qc"),
        "uuid": cookie.get("userId", ""),
        "openid": cookie.get("openid", ""),
        "source_game_zone": "agame",
        "game_zone": "agame",
    }
    result = api_post(session, "/go/auth/refresh_third_token", body)
    if result.get("result") == 0:
        token = result.get("data", {}).get("access_token", "")
        if token:
            session.cookies.set("access_token", token, domain="app.mval.qq.com")
            save_persisted_token(acc_name, "at", token)
            print(f"🔄 【{acc_name}】access_token 自动刷新成功并已持久化保存")
            return token
    print(f"⚠️ 【{acc_name}】access_token 自动刷新失败: {result.get('msg', '未知原因')}")
    return ""


def refresh_web_ticket(session: requests.Session, acc_name: str, ct: str) -> tuple:
    """刷新并保存 web ticket (tid) 以及 client ticket (ct)"""
    cookie = {c.name: c.value for c in session.cookies}
    user_id = cookie.get("userId", "")

    # 第一步：刷新 client ticket (ct) 获得新 ct 和 wt (也就是 tid)
    rct_body = {
        "config_params": {"lang_type": 0},
        "ct": ct,
        "local_is_new_user": 0,
        "user_id": user_id,
        "source_game_zone": "agame",
        "game_zone": "agame",
    }
    rct_result = api_post(session, "/go/auth/refresh_client_ticket", rct_body)
    if rct_result.get("result") != 0:
        print(f"⚠️ 【{acc_name}】refresh_client_ticket 失败: {rct_result.get('msg', '未知原因')}")
        return ct, False

    rct_data = rct_result.get("data", {})
    ct_info = rct_data.get("ct_info", rct_data)
    new_ct = ct_info.get("ct", "")
    wt = ct_info.get("wt", "")

    if new_ct:
        save_persisted_token(acc_name, "ct", new_ct)
        print(f"🔄 【{acc_name}】client ticket (ct) 刷新成功并已持久化保存")
    if wt:
        # 更新 tid
        tid_set = False
        for c in session.cookies:
            if c.name == "tid":
                c.value = wt
                tid_set = True
                break
        if not tid_set:
            session.cookies.set("tid", wt, domain="app.mval.qq.com", path="/")
        print(f"🔄 【{acc_name}】web ticket (tid) 刷新成功")

    if not new_ct:
        return ct, False

    # 第二步：获取临时凭证 ctt 和 sk
    ctt_body = {
        "config_params": {"lang_type": 0},
        "ct": new_ct,
    }
    api_post(session, "/go/auth/get_client_tmp_ticket", ctt_body)

    return new_ct, bool(wt)


# ==============================================================================
# 6. 微信鉴权
# ==============================================================================
def get_wechat_access_token():
    token_url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={APP_ID}&secret={APP_SECRET}"
    try:
        res = requests.get(token_url, timeout=10).json()
        token = res.get("access_token")
        if not token:
            print(f"❌ 获取微信 Access Token 失败: {res}")
        return token
    except Exception as e:
        print(f"❌ 微信鉴权网络异常: {e}")
        return None


# ==============================================================================
# 7. 单个账号查询、自动刷新与推送处理
# ==============================================================================
def process_account(wechat_token: str, acc: dict):
    acc_name = acc.get("name", "未命名账号")
    target_openid = acc.get("open_id", "")
    fav_set = acc.get("fav_set", set())
    raw_cookie = acc.get("cookie", "")

    if not raw_cookie:
        print(f"❌ 【{acc_name}】未配置 cookie，跳过执行")
        return

    print(f"\n🔍 正在处理账号: 【{acc_name}】...")

    # 1. 建立 Session 并载入本地持久化 Token
    session = create_session(acc_name, raw_cookie)
    
    cookie_dict = parse_cookie(raw_cookie)
    initial_ct = cookie_dict.get("ct", "")
    ct = load_persisted_token(acc_name, "ct", initial_ct)

    if not ct:
        print(f"❌ 【{acc_name}】缺少必要的 ct (client ticket) 参数，无法进行持久化自动登录。")
        return

    # 2. 尝试双重刷新，自动延长 Cookie 的有效期
    refresh_token(session, acc_name)
    _, ct_ok = refresh_web_ticket(session, acc_name, ct)
    if not ct_ok:
        print(f"⚠️ 【{acc_name}】Token 刷新返回异常，可能是首次运行或原 Cookie 已完全过期，尝试直接请求商店。")

    # 3. 发起商店请求
    try:
        store_data = api_post(session, "/go/mlol_store/agame/user_store", {
            "scene": "",
            "source_game_zone": "agame",
            "game_zone": "agame",
        })
    except Exception as e:
        print(f"❌ 【{acc_name}】请求官方商店接口发生网络异常: {e}")
        return

    # 4. 检查账号是否过期
    if store_data.get("result") != 0:
        err_msg = store_data.get("err_msg", store_data.get("msg", "Cookie 彻底过期，自动续期失效"))
        print(f"❌ 【{acc_name}】授权已失效: {err_msg}")
        send_to_wechat(wechat_token, target_openid, {
            "title": {"value": f"⚠️【{acc_name}】授权已完全失效", "color": COLOR_WISH},
            "skin1": {"value": "请重新抓包并在 GitHub Secrets 中更新 Cookie", "color": COLOR_WISH},
            "skin2": {"value": f"系统错误: {err_msg}", "color": "#7F8C8D"},
            "skin3": {"value": "-", "color": "#999999"},
            "skin4": {"value": "-", "color": "#999999"},
            "wish": {"value": "自动续期失败", "color": COLOR_WISH},
            "kingdom": {"value": "-", "color": "#999999"}
        })
        return

    # 5. 提取每日商店与王国商店
    daily_items = []
    kingdom_items = []
    remaining_sec = 0

    for module in store_data.get("data", []):
        key = module.get("key")
        if key == "dailystore":
            # 兼容：优先读取 "time" 属性；如果缺失则利用 "end_ts" 减去当前时间计算
            remaining_sec = module.get("time", 0)
            if not remaining_sec and module.get("end_ts"):
                remaining_sec = max(0, int(module.get("end_ts") - time.time()))
            daily_items = module.get("list", [])
        elif key == "kingdomstore":
            kingdom_items = module.get("list", [])

    # 6. 计算倒计时与日期
    d_h = remaining_sec // 3600
    d_m = (remaining_sec % 3600) // 60
    bj_time = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    today_str = bj_time.strftime("%m月%d日")

    title_text = f"🎮 商店【{acc_name}】({today_str} 剩{d_h}h{d_m}m)"

    # 7. 心愿匹配
    hit_wanted = [f"【{item.get('goods_name')}】" for item in daily_items if item.get("goods_name") in fav_set]
    wish_text = f"🎯 命中心愿: {' '.join(hit_wanted)}！速买！" if hit_wanted else "今日未刷出心愿皮肤"
    wish_color = COLOR_WISH if hit_wanted else "#7F8C8D"

    # 8. 王国配件
    k_names = [k.get("goods_name", "").split(" ")[0] for k in kingdom_items]
    kingdom_text = "、".join(k_names) if k_names else "无"

    # 9. 组装微信模板数据
    template_data = {
        "title": {"value": title_text, "color": "#111111"},
        "wish": {"value": wish_text, "color": wish_color},
        "kingdom": {"value": kingdom_text, "color": "#16A085"}
    }

    for i in range(4):
        slot = f"skin{i+1}"
        if i < len(daily_items):
            item = daily_items[i]
            name = item.get("goods_name", "未知")
            price = item.get("rmb_price", "0")
            quality = item.get("quality", "normal")

            if name in fav_set:
                skin_str = f"🔥 {name} - {price}点券 (🎯命中)"
                color = COLOR_WISH
            else:
                skin_str = f"{name} - {price}点券"
                color = QUALITY_COLORS.get(quality, "#333333")

            template_data[slot] = {"value": skin_str, "color": color}
        else:
            template_data[slot] = {"value": "-", "color": "#999999"}

    # 10. 发送微信推送
    send_to_wechat(wechat_token, target_openid, template_data)


# ==============================================================================
# 8. 底层消息发送（强制 UTF-8）
# ==============================================================================
def send_to_wechat(token: str, target_openid: str, template_data: dict):
    send_url = f"https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={token}"
    body = {
        "touser": target_openid.strip(),
        "template_id": TEMPLATE_ID,
        "data": template_data
    }
    
    headers = {"Content-Type": "application/json; charset=utf-8"}
    data_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")
    
    try:
        resp = requests.post(send_url, data=data_bytes, headers=headers, timeout=10).json()
        if resp.get("errcode") == 0:
            print(f"🎉 微信推送成功！")
        else:
            print(f"❌ 微信推送失败: {resp}")
    except Exception as e:
        print(f"❌ 微信推送网络异常: {e}")


# ==============================================================================
# 9. 主执行流程
# ==============================================================================
def main():
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🚀 开始执行多账号商店检查与自动续期...")

    wechat_token = get_wechat_access_token()
    if not wechat_token:
        print("❌ 无法获取微信 Access Token，程序中止")
        return

    # 循环执行每个账号
    for account in ACCOUNTS:
        process_account(wechat_token, account)
        # 账号之间间隔 2.5 秒，防止被腾讯或微信接口限频
        time.sleep(2.5)

    print("\n✅ 所有账号检查完毕！")


if __name__ == "__main__":
    main()
