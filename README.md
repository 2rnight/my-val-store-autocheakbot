# 掌上无畏契约每日商店推送

每天自动查询《掌上无畏契约》每日商店，并通过微信模板消息推送给你。

## 🎬 效果

<!-- 图片占位：推送效果预览，插入时替换为 ![推送效果预览](images/preview.png) -->
> 📷 **[图片占位]** 推送效果预览

## 📋 前置准备

### 1. 注册微信公众号测试号

1. 访问 微信公众平台测试号，使用微信扫码登录
2. 记录页面上的 `appID` 和 `appSecret`
3. 在 **模板消息接口** 区域点击 **新增测试模板**，填写以下内容：
   - 模板标题：`每日商店推送`
   - 模板内容：

     ```text
     {{title.DATA}}
     皮肤1：{{skin1.DATA}}
     皮肤2：{{skin2.DATA}}
     皮肤3：{{skin3.DATA}}
     皮肤4：{{skin4.DATA}}
     {{wish.DATA}}
     王国商店：{{kingdom.DATA}}
     ```

4. 记录生成的 **模板 ID**
5. 在 **测试号二维码** 处扫码关注，记录你的微信号（即 `open_id`）

<!-- 图片占位：测试号页面（appID / appSecret 位置），插入时替换为 ![测试号页面](images/sandbox.png) -->
> 📷 **[图片占位]** 测试号页面（appID / appSecret 位置）

<!-- 图片占位：模板消息配置，插入时替换为 ![模板配置](images/template.png) -->
> 📷 **[图片占位]** 模板消息配置

### 2. 抓包获取游戏 Cookie

1. 在手机上安装抓包工具（推荐 Stream (iOS) / HttpCanary (Android)）
2. 打开 掌上无畏契约 App，登录后查看每日商店
3. 在抓包工具中找到请求域名 `app.mval.qq.com` 的 `refresh_client_ticket` 请求
4. 复制该请求的完整 Cookie 请求头，并将 `ct` 拼接在 Cookie 末尾，格式如下：

   ```text
   clientType=xxx; uin=xxx; appid=xxx; acctype=xx; openid=xxx; access_token=xxx; userId=xxx; accountType=xx; tid=xx; ct=xxx
   ```

> [!NOTE]
> 微信端没有 `uin` 字段。

<!-- 图片占位：抓包请求页面（refresh_client_ticket），插入时替换为 ![抓包请求](images/capture.png) -->
> 📷 **[图片占位]** 抓包请求页面（refresh_client_ticket）

## ⚙️ 配置步骤

### 1. Fork 本仓库

点击右上角 **Fork** 按钮，将仓库复制到你的 GitHub 账号下。

> [!WARNING]
> 🔒 强烈建议：Fork 后将仓库设置为 **Private（私有）**，以保护你的 Cookie 和微信密钥。

### 2. 配置 GitHub Secrets

进入你的仓库 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**，依次添加以下 4 个 Secret：

| Secret 名称 | 值 | 说明 |
| --- | --- | --- |
| `APP_ID` | `wx1234567890abcdef` | 微信测试号的 appID |
| `APP_SECRET` | `abcdef1234567890...` | 微信测试号的 appSecret |
| `TEMPLATE_ID` | `AbCdEfGhIjKlMnOpQrStUvWxYz...` | 微信模板消息的模板 ID |
| `ACCOUNTS_JSON` | 见 [填写 ACCOUNTS_JSON](#3-填写-accounts_json) | 多账号配置（JSON 格式） |

<!-- 图片占位：Secrets 配置页面，插入时替换为 ![Secrets 配置](images/secrets.png) -->
> 📷 **[图片占位]** Secrets 配置页面

### 3. 填写 ACCOUNTS_JSON

`ACCOUNTS_JSON` 的值是一个 JSON 数组，每个元素代表一个游戏账号：

```json
[
  {
    "name": "大号",
    "open_id": "oXxXxXxXxXxXxXxXxXxXxXxXx",
    "cookie": "userId=123456; ct=abcdef...; openid=xxx; acctype=qc; access_token=xxx; tid=xxx",
    "fav_set": ["混沌序幕 暴徒", "掠夺狂潮 幻影", "异星霸主 冥驹"]
  },
  {
    "name": "小号",
    "open_id": "oYyYyYyYyYyYyYyYyYyYyYyYy",
    "cookie": "userId=789012; ct=ghijkl...; openid=yyy; acctype=wx; access_token=yyy; tid=yyy",
    "fav_set": ["盖亚的复仇 狂徒"]
  }
]
```

**字段说明：**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | :---: | --- |
| `name` | 字符串 | ✅ | 账号昵称，用于推送标题区分 |
| `open_id` | 字符串 | ✅ | 接收推送的微信 `open_id` |
| `cookie` | 字符串 | ✅ | 抓包获取的完整 Cookie 字符串 |
| `fav_set` | 数组 | ❌ | 心愿皮肤名称列表，命中时高亮提醒 |

<!-- 图片占位：ACCOUNTS_JSON 填写示例，插入时替换为 ![ACCOUNTS_JSON 示例](images/accounts-json.png) -->
> 📷 **[图片占位]** ACCOUNTS_JSON 填写示例

### 4. 测试

1. 进入仓库的 **Actions** 页面
2. 点击 **掌上无畏契约每日商店推送** 工作流
3. 点击 **Run workflow** 手动运行一次，检查微信是否收到推送
