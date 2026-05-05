from app import create_app

app = create_app()

if __name__ == '__main__':
    print("=" * 50)
    print("  红色足迹：韶山之旅 - 游戏服务器")
    print("  韶山红色文化教育游戏")
    print("=" * 50)
    print("\n正在启动服务器...")
    print("后端API: http://localhost:5000/api")
    print("前端页面: http://localhost:5000/")
    print("\n按 Ctrl+C 停止服务器")
    print("-" * 50)

    app.run(debug=True, host='0.0.0.0', port=5000)
