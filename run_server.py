"""启动服务器脚本，从配置文件读取端口和主机."""
import uvicorn
from app.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    print("========================================")
    print(f"Starting server on {settings.app_host}:{settings.app_port}...")
    print("========================================")
    print()
    
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False
    )
