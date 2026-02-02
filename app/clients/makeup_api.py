"""Makeup API client封装."""
import random
import time
from typing import Any, Dict, Optional

import httpx

from app.config import get_settings

settings = get_settings()


class MakeupApiClient:
    """HTTP 客户端，负责调用 makeup 接口."""

    def __init__(self) -> None:
        base_url = str(settings.makeup_api_base_url)
        self.base_url = base_url.rstrip("/")
        self.timeout = settings.makeup_api_timeout
        self.max_retries = settings.makeup_api_max_retries
        # 打印当前使用的API地址，方便确认
        print(f"[MakeupApiClient] 初始化完成，API地址: {self.base_url}")
        if "localhost" in self.base_url or "127.0.0.1" in self.base_url:
            print(f"[MakeupApiClient] ⚠️  警告: 当前使用的是本地地址，请确认是否需要切换到线上地址")

    def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """带重试的请求."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        last_err: Optional[Exception] = None
        
        # 打印请求信息
        print(f"[MakeupApiClient] ====== 发起请求 ======")
        print(f"[MakeupApiClient] 请求地址: {method} {url}")
        if params:
            print(f"[MakeupApiClient] 请求参数: {params}")
        if json:
            # 隐藏敏感信息（如密码）
            safe_json = {k: ("***" if k in ["password", "code"] else v) for k, v in json.items()}
            print(f"[MakeupApiClient] 请求体: {safe_json}")
        if headers:
            # 隐藏token
            safe_headers = {k: ("***" if k.lower() == "token" else v) for k, v in headers.items()}
            print(f"[MakeupApiClient] 请求头: {safe_headers}")
        
        for attempt in range(1, self.max_retries + 1):
            try:
                # follow_redirects 避免 301/302 返回 HTML 导致 JSON 解析失败
                resp = httpx.request(
                    method,
                    url,
                    json=json,
                    headers=headers,
                    params=params,
                    timeout=self.timeout,
                    follow_redirects=True,
                )
                
                # 打印响应状态
                print(f"[MakeupApiClient] 响应状态: {resp.status_code} {resp.reason_phrase}")
                
                resp.raise_for_status()
                print(f"[MakeupApiClient] ✓ 请求成功")
                return resp
            except httpx.HTTPStatusError as exc:
                # 打印详细的HTTP错误信息
                print(f"[MakeupApiClient] ✗ HTTP错误 (尝试 {attempt}/{self.max_retries})")
                print(f"[MakeupApiClient] 状态码: {exc.response.status_code}")
                print(f"[MakeupApiClient] 响应头: {dict(exc.response.headers)}")
                
                # 如果是HTTP错误，尝试解析响应内容
                try:
                    error_data = exc.response.json()
                    error_msg = error_data.get("message", error_data.get("error", str(exc)))
                    print(f"[MakeupApiClient] 错误信息 (JSON): {error_data}")
                    raise RuntimeError(f"API error: {error_msg}") from exc
                except Exception:
                    # 如果响应不是JSON，返回原始响应文本
                    error_text = exc.response.text[:500]  # 增加长度以便查看
                    print(f"[MakeupApiClient] 错误信息 (非JSON): {error_text}")
                    raise RuntimeError(f"API error (non-JSON): {error_text}") from exc
            except httpx.RequestError as exc:
                # 网络请求错误（连接失败、超时等）
                print(f"[MakeupApiClient] ✗ 网络请求错误 (尝试 {attempt}/{self.max_retries}): {type(exc).__name__}: {exc}")
                last_err = exc
                if attempt < self.max_retries:
                    sleep_for = min(2 ** attempt + random.random(), 10)
                    print(f"[MakeupApiClient] 等待 {sleep_for:.2f} 秒后重试...")
                    time.sleep(sleep_for)
            except Exception as exc:  # noqa: PERF203
                print(f"[MakeupApiClient] ✗ 未知错误 (尝试 {attempt}/{self.max_retries}): {type(exc).__name__}: {exc}")
                last_err = exc
                if attempt < self.max_retries:
                    sleep_for = min(2 ** attempt + random.random(), 10)
                    print(f"[MakeupApiClient] 等待 {sleep_for:.2f} 秒后重试...")
                    time.sleep(sleep_for)
        
        print(f"[MakeupApiClient] ✗✗✗ 所有重试均失败 ✗✗✗")
        raise RuntimeError(f"Request failed after {self.max_retries} retries: {last_err}")  # pragma: no cover

    def register(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """注册接口."""
        resp = self._request("POST", "/auth/register", json=payload)
        try:
            return resp.json()
        except Exception as exc:
            # 如果响应不是JSON，返回错误信息
            error_text = resp.text[:500] if hasattr(resp, 'text') else str(exc)
            return {"code": "error", "message": f"Invalid JSON response: {error_text}"}

    def login(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """登录接口."""
        resp = self._request("POST", "/auth/login", json=payload)
        try:
            return resp.json()
        except Exception as exc:
            # 如果响应不是JSON，返回错误信息
            error_text = resp.text[:500] if hasattr(resp, 'text') else str(exc)
            return {"code": "error", "message": f"Invalid JSON response: {error_text}"}

    def refresh_token(self, token: str) -> Dict[str, Any]:
        """
        刷新token接口（使用旧token获取新token）。
        
        @param token - 当前token
        @returns 包含新token的响应
        """
        headers = {"Token": token}
        resp = self._request("POST", "/auth/refresh", headers=headers)
        try:
            return resp.json()
        except Exception as exc:
            # 如果响应不是JSON，返回错误信息
            error_text = resp.text[:500] if hasattr(resp, 'text') else str(exc)
            return {"code": "error", "message": f"Invalid JSON response: {error_text}"}

    def post_content(self, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """发布动态."""
        headers = {"Token": token}
        resp = self._request("POST", "/api/community/posts", json=payload, headers=headers)
        return resp.json()

    def apply_makeup(self, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """设置妆容."""
        headers = {"Token": token}
        resp = self._request("POST", "/api/makeup", json=payload, headers=headers)
        return resp.json()

    def send_verify_code(self, email: str, code_type: str = "register") -> None:
        """发送验证码或验证链接."""
        payload = {"email": email, "type": code_type}
        self._request("POST", "/auth/code", json=payload)

    def get_ai_names(self) -> Dict[str, Any]:
        """获取 AI 名称列表."""
        resp = self._request("GET", "/auth/users/ai-names")
        return resp.json()

    def get_avatars(self, type_: int = 0, page: int = 1, size: int = 10) -> Dict[str, Any]:
        """获取系统头像列表."""
        resp = self._request("GET", "/auth/users/avatars", params={"type": type_, "page": page, "size": size})
        try:
            return resp.json()
        except Exception as exc:
            # 如果响应不是JSON，返回错误信息
            error_text = resp.text[:500] if hasattr(resp, 'text') else str(exc)
            return {"code": "error", "message": f"Invalid JSON response: {error_text}"}

    def get_user_info(self, token: str) -> Dict[str, Any]:
        """获取当前用户信息."""
        headers = {"Token": token}
        resp = self._request("GET", "/api/users/info", headers=headers)
        try:
            return resp.json()
        except Exception as exc:
            error_text = resp.text[:500] if hasattr(resp, 'text') else str(exc)
            return {"code": "error", "message": f"Invalid JSON response: {error_text}"}

    def update_user_info(self, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """修改个人信息."""
        headers = {"Token": token}
        resp = self._request("PUT", "/api/users/info", json=payload, headers=headers)
        try:
            return resp.json()
        except Exception as exc:
            # 如果响应不是JSON，返回错误信息
            error_text = resp.text[:500] if hasattr(resp, 'text') else str(exc)
            return {"code": "error", "message": f"Invalid JSON response: {error_text}"}

    def send_change_password_code(self, token: str, method: str = "email") -> Dict[str, Any]:
        """发送修改密码验证码."""
        headers = {"Token": token}
        resp = self._request("POST", "/api/users/password/verify/send-code", json={"method": method}, headers=headers)
        return resp.json()

    def change_password_verify(self, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """验证身份获取修改密码 token."""
        headers = {"Token": token}
        resp = self._request("POST", "/api/users/password/verify", json=payload, headers=headers)
        return resp.json()

    def change_password(self, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """修改密码."""
        headers = {"Token": token}
        resp = self._request("PUT", "/api/users/password", json=payload, headers=headers)
        return resp.json()

    def update_preferences(self, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """更新偏好设置."""
        headers = {"Token": token}
        resp = self._request("PUT", "/api/users/preferences", json=payload, headers=headers)
        return resp.json()

    def checkin_today(self, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """今日签到."""
        headers = {"Token": token}
        resp = self._request("POST", "/api/beauty/checkin", json=payload, headers=headers)
        return resp.json()

    def face_save(self, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """保存人脸."""
        headers = {"Token": token}
        resp = self._request("POST", "/api/beauty/face/save", json=payload, headers=headers)
        return resp.json()

    def face_validate(self, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """校验人脸图片（模拟上传前校验）."""
        headers = {"Token": token}
        resp = self._request("POST", "/api/beauty/face/validate", json=payload, headers=headers)
        return resp.json()

    def face_list(self, token: str) -> Dict[str, Any]:
        """获取人脸列表."""
        headers = {"Token": token}
        resp = self._request("GET", "/api/beauty/face/list", headers=headers)
        return resp.json()

    def editor_session(self, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """创建编辑会话."""
        headers = {"Token": token}
        resp = self._request("POST", "/api/beauty/editor/session", json=payload, headers=headers)
        return resp.json()

    def editor_step(self, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """编辑单步."""
        headers = {"Token": token}
        print(f"[API] editor_step request payload: {payload}")
        resp = self._request("POST", "/api/beauty/editor/step", json=payload, headers=headers)
        result = resp.json()
        print(f"[API] editor_step response: {result}")
        return result

    def editor_save(self, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """保存编辑为妆容."""
        headers = {"Token": token}
        resp = self._request("POST", "/api/beauty/editor/save", json=payload, headers=headers)
        return resp.json()

    def my_makeups(self, token: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """获取我的妆容列表."""
        headers = {"Token": token}
        resp = self._request("GET", "/api/beauty/makeups", headers=headers, params=params or {})
        return resp.json()

    def makeups_list(self, token: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """获取全部妆容列表."""
        headers = {"Token": token}
        resp = self._request("GET", "/api/beauty/makeups/list", headers=headers, params=params or {})
        return resp.json()

    def makeup_tags(self, token: str) -> Dict[str, Any]:
        """获取妆造标签."""
        headers = {"Token": token}
        resp = self._request("GET", "/api/beauty/makeup/tags", headers=headers)
        return resp.json()

    def topics(self, token: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """获取话题列表."""
        headers = {"Token": token}
        resp = self._request("GET", "/api/beauty/topics", headers=headers, params=params or {})
        return resp.json()

    def topics_categories(self, token: str) -> Dict[str, Any]:
        """获取话题分类."""
        headers = {"Token": token}
        resp = self._request("GET", "/api/beauty/topics/categories", headers=headers)
        return resp.json()

    def topic_collect(self, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """收藏话题."""
        headers = {"Token": token}
        resp = self._request("POST", "/api/beauty/topics/collect", json=payload, headers=headers)
        return resp.json()

    def generate_post_content(self, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """生成AI文案."""
        headers = {"Token": token}
        resp = self._request("POST", "/api/beauty/community/post/generate-content", json=payload, headers=headers)
        return resp.json()

    def check_post_count(self, token: str, makeup_type: str, makeup_id: int) -> Dict[str, Any]:
        """
        查询是否已发布过动态。
        @param token - 用户token
        @param makeup_type - 妆容类型，如 "user_makeup"
        @param makeup_id - 妆容ID
        @returns 包含count字段的响应，count > 0 表示已发布过
        """
        headers = {"Token": token}
        params = {
            "makeup_type": makeup_type,
            "makeup_id": makeup_id,
        }
        resp = self._request("GET", "/api/beauty/community/post/count", headers=headers, params=params)
        return resp.json()
    
    def create_post(self, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """创建社区动态."""
        headers = {"Token": token}
        resp = self._request("POST", "/api/beauty/community/post", json=payload, headers=headers)
        return resp.json()

    def like_post(self, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """点赞动态/妆造."""
        headers = {"Token": token}
        resp = self._request("POST", "/api/beauty/community/post/like", json=payload, headers=headers)
        return resp.json()

    def comment(self, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """发表评论."""
        headers = {"Token": token}
        resp = self._request("POST", "/api/beauty/community/comment", json=payload, headers=headers)
        return resp.json()

    def comments(self, token: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """获取评论列表."""
        headers = {"Token": token}
        resp = self._request("GET", "/api/beauty/community/comments", headers=headers, params=params or {})
        return resp.json()

    def like_comment(self, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """点赞评论."""
        headers = {"Token": token}
        resp = self._request("POST", "/api/beauty/community/comment/like", json=payload, headers=headers)
        return resp.json()

    def collect_try_record(self, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """收藏试妆记录."""
        headers = {"Token": token}
        resp = self._request("POST", "/api/space/try-records/collect", json=payload, headers=headers)
        return resp.json()

    def get_try_history(self, token: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """获取试妆历史."""
        headers = {"Token": token}
        resp = self._request("GET", "/api/beauty/try-history", headers=headers, params=params or {})
        return resp.json()

    def collect_makeup(self, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """收藏妆造."""
        headers = {"Token": token}
        resp = self._request("POST", "/api/space/collections", json=payload, headers=headers)
        return resp.json()

    def follow_user(self, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """关注用户."""
        headers = {"Token": token}
        # 后端要求 target_user_id；为兼容历史调用，这里把 user_id 映射为 target_user_id
        if isinstance(payload, dict) and "target_user_id" not in payload and "user_id" in payload:
            payload = {**payload, "target_user_id": payload.get("user_id")}
            payload.pop("user_id", None)
        resp = self._request("POST", "/api/beauty/follow", json=payload, headers=headers)
        return resp.json()

    def get_templates(self, token: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """获取妆容模板列表."""
        headers = {"Token": token}
        resp = self._request("GET", "/api/beauty/templates", headers=headers, params=params or {})
        return resp.json()

    def get_template_detail(self, token: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """获取妆容模板详情."""
        headers = {"Token": token}
        resp = self._request("GET", "/api/beauty/templates/detail", headers=headers, params=params or {})
        return resp.json()

    def get_makeup_detail(self, token: str, makeup_id: int) -> Dict[str, Any]:
        """获取妆造详情."""
        headers = {"Token": token}
        resp = self._request("GET", f"/api/beauty/makeups/detail", headers=headers, params={"makeup_id": makeup_id})
        return resp.json()

    def get_community_feed(self, token: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """获取社区动态流."""
        headers = {"Token": token}
        resp = self._request("GET", "/api/beauty/community/feed", headers=headers, params=params or {})
        return resp.json()

    def get_post_detail(self, token: str, post_id: int) -> Dict[str, Any]:
        """获取动态详情."""
        headers = {"Token": token}
        resp = self._request("GET", "/api/beauty/community/post", headers=headers, params={"post_id": post_id})
        return resp.json()


