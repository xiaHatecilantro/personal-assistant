# 运行环境

## Python 虚拟环境

项目后端**必须**使用 Conda 虚拟环境 `personal-assistant`。

- **Python 路径**：`D:/Miniconda3/envs/personal-assistant/python.exe`
- **pip 路径**：`D:/Miniconda3/envs/personal-assistant/Scripts/pip.exe`
- **环境名**：`personal-assistant`

### 命令执行方式

由于 bash shell 未初始化 conda，所有 Python 相关命令必须使用**绝对路径**：

```bash
# 运行后端
"D:/Miniconda3/envs/personal-assistant/python.exe" -m uvicorn app.main:app --reload

# 安装依赖
"D:/Miniconda3/envs/personal-assistant/Scripts/pip.exe" install <package>

# 运行脚本
"D:/Miniconda3/envs/personal-assistant/python.exe" <script.py>
```

### 注意
- 不要使用系统全局 Python（`C:\Users\Xia chuan can\AppData\Local\Programs\Python\`）
- 不要使用 `python` 或 `pip` 裸命令——它们指向系统全局版本
- 前端（Node.js）不受此限制，正常使用 `npm`/`pnpm` 即可
