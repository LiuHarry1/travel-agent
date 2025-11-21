# Docker 构建问题解决指南

## 问题：网络超时无法拉取基础镜像

### 解决方案 1: 配置 Docker 镜像加速器（推荐）

这是最简单有效的方法，配置一次后所有构建都会加速。

#### macOS/Windows (Docker Desktop)

1. 打开 Docker Desktop
2. 点击设置图标（齿轮）
3. 进入 **Docker Engine**
4. 在 JSON 配置中添加：

```json
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com",
    "https://dockerhub.azk8s.cn"
  ]
}
```

5. 点击 **Apply & Restart**
6. 等待 Docker 重启完成

#### Linux

编辑 `/etc/docker/daemon.json`（如果不存在则创建）：

```json
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com"
  ]
}
```

然后重启 Docker：

```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
```

### 解决方案 2: 手动拉取镜像后构建

```bash
# 先手动拉取基础镜像（可以多次重试）
docker pull python:3.11-slim

# 如果还是超时，尝试使用代理
export HTTP_PROXY=http://your-proxy:port
export HTTPS_PROXY=http://your-proxy:port
docker pull python:3.11-slim

# 拉取成功后，正常构建
docker build -t mrt-review-backend:latest .
```

### 解决方案 3: 使用国内镜像源构建

如果配置了镜像加速器后仍然有问题，可以使用 `Dockerfile.mirror`：

```bash
docker build -f Dockerfile.mirror -t mrt-review-backend:latest .
```

这个 Dockerfile 会：
- 使用官方镜像（通过已配置的镜像加速器）
- 配置 pip 使用国内 PyPI 镜像源（加速 Python 包安装）

### 解决方案 4: 使用代理

如果有可用的代理：

```bash
# 设置代理
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890

# 构建
docker build -t mrt-review-backend:latest .
```

或者在 Docker Desktop 中配置代理：
1. Settings > Resources > Proxies
2. 配置代理设置

### 解决方案 5: 使用预构建的基础镜像

如果以上方法都不行，可以尝试：

```bash
# 从其他源拉取 Python 镜像
docker pull registry.cn-hangzhou.aliyuncs.com/google_containers/python:3.11-slim

# 打标签
docker tag registry.cn-hangzhou.aliyuncs.com/google_containers/python:3.11-slim python:3.11-slim

# 然后正常构建
docker build -t mrt-review-backend:latest .
```

## 验证镜像加速器配置

配置完成后，验证是否生效：

```bash
docker info | grep -A 10 "Registry Mirrors"
```

应该能看到你配置的镜像地址。

## 常见问题

### Q: 配置镜像加速器后仍然超时？

A: 尝试：
1. 更换其他镜像源
2. 检查网络连接
3. 使用代理

### Q: pip 安装包也很慢？

A: `Dockerfile.mirror` 已经配置了 pip 使用国内源，如果使用原始 Dockerfile，可以在构建时添加：

```dockerfile
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/
```

### Q: 如何知道哪个镜像源最快？

A: 可以测试不同镜像源的连接速度：

```bash
# 测试中科大镜像
time docker pull docker.mirrors.ustc.edu.cn/library/python:3.11-slim

# 测试网易镜像
time docker pull hub-mirror.c.163.com/library/python:3.11-slim
```

