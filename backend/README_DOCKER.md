# Docker 部署指南

## 构建 Docker 镜像

### 方式 1: 使用官方镜像（需要良好的网络连接）

在 `backend` 目录下执行：

```bash
docker build -t mrt-review-backend:latest .
```

### 方式 2: 使用国内镜像源（推荐，适用于国内网络）

如果遇到网络超时问题，可以使用国内镜像源：

```bash
# 使用阿里云镜像源
docker build -f Dockerfile.mirror -t mrt-review-backend:latest .

# 或者使用腾讯云镜像源（修改 Dockerfile.mirror 中的 FROM 行）
```

### 方式 3: 配置 Docker 镜像加速器

在 Docker Desktop 中配置镜像加速器：

1. 打开 Docker Desktop
2. 进入 Settings > Docker Engine
3. 添加以下配置：

```json
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com"
  ]
}
```

4. 点击 "Apply & Restart"
5. 然后使用原始 Dockerfile 构建：

```bash
docker build -t mrt-review-backend:latest .
```

### 方式 4: 使用代理

如果有代理，可以配置 Docker 使用代理：

```bash
# 设置代理环境变量
export HTTP_PROXY=http://your-proxy:port
export HTTPS_PROXY=http://your-proxy:port

# 然后构建
docker build -t mrt-review-backend:latest .
```

## 推送到 Docker 仓库

### 方式 1: Docker Hub

1. **登录 Docker Hub**：

```bash
docker login
# 输入你的 Docker Hub 用户名和密码
```

2. **给镜像打标签**（使用你的 Docker Hub 用户名）：

```bash
docker tag mrt-review-backend:latest your-username/mrt-review-backend:latest
# 或者指定版本号
docker tag mrt-review-backend:latest your-username/mrt-review-backend:v1.0.0
```

3. **推送镜像**：

```bash
# 推送 latest 标签
docker push your-username/mrt-review-backend:latest

# 推送版本标签
docker push your-username/mrt-review-backend:v1.0.0
```

### 方式 2: 阿里云容器镜像服务 (ACR)

1. **登录阿里云容器镜像服务**：

```bash
docker login --username=your-username registry.cn-hangzhou.aliyuncs.com
# 输入密码（在阿里云控制台获取）
```

2. **给镜像打标签**：

```bash
docker tag mrt-review-backend:latest registry.cn-hangzhou.aliyuncs.com/your-namespace/mrt-review-backend:latest
# 或者使用其他地域的 registry
# registry.cn-beijing.aliyuncs.com
# registry.cn-shanghai.aliyuncs.com
# registry.cn-shenzhen.aliyuncs.com
```

3. **推送镜像**：

```bash
docker push registry.cn-hangzhou.aliyuncs.com/your-namespace/mrt-review-backend:latest
```

### 方式 3: 腾讯云容器镜像服务 (TCR)

1. **登录腾讯云容器镜像服务**：

```bash
docker login ccr.ccs.tencentyun.com
# 输入用户名和密码
```

2. **给镜像打标签**：

```bash
docker tag mrt-review-backend:latest ccr.ccs.tencentyun.com/your-namespace/mrt-review-backend:latest
```

3. **推送镜像**：

```bash
docker push ccr.ccs.tencentyun.com/your-namespace/mrt-review-backend:latest
```

### 方式 4: GitHub Container Registry (ghcr.io)

1. **创建 Personal Access Token (PAT)**：
   - 访问 GitHub Settings > Developer settings > Personal access tokens
   - 创建 token，需要 `write:packages` 权限

2. **登录 GitHub Container Registry**：

```bash
echo $GITHUB_TOKEN | docker login ghcr.io -u your-username --password-stdin
# 或者直接输入密码
docker login ghcr.io -u your-username
```

3. **给镜像打标签**：

```bash
docker tag mrt-review-backend:latest ghcr.io/your-username/mrt-review-backend:latest
```

4. **推送镜像**：

```bash
docker push ghcr.io/your-username/mrt-review-backend:latest
```

### 方式 5: 私有 Docker Registry

1. **登录私有仓库**：

```bash
docker login your-registry.com:5000
# 输入用户名和密码
```

2. **给镜像打标签**：

```bash
docker tag mrt-review-backend:latest your-registry.com:5000/mrt-review-backend:latest
```

3. **推送镜像**：

```bash
docker push your-registry.com:5000/mrt-review-backend:latest
```

## 使用推送脚本（推荐）

我们提供了一个便捷的推送脚本：

```bash
# 推送到 Docker Hub
./scripts/push_image.sh dockerhub your-username v1.0.0

# 推送到阿里云
./scripts/push_image.sh aliyun your-namespace v1.0.0 cn-hangzhou

# 推送到腾讯云
./scripts/push_image.sh tencent your-namespace v1.0.0

# 推送到 GitHub Container Registry
export GITHUB_TOKEN=your_token
./scripts/push_image.sh github your-username v1.0.0
```

## 从仓库拉取和运行

推送成功后，可以在任何地方拉取镜像：

```bash
# Docker Hub
docker pull your-username/mrt-review-backend:latest

# 阿里云
docker pull registry.cn-hangzhou.aliyuncs.com/your-namespace/mrt-review-backend:latest

# 腾讯云
docker pull ccr.ccs.tencentyun.com/your-namespace/mrt-review-backend:latest

# GitHub
docker pull ghcr.io/your-username/mrt-review-backend:latest
```

然后运行：

```bash
docker run -d \
  --name mrt-review-backend \
  -p 8000:8000 \
  -e DASHSCOPE_API_KEY=your_api_key_here \
  your-username/mrt-review-backend:latest
```

## 快速参考

### 常用命令

```bash
# 查看本地镜像
docker images | grep mrt-review-backend

# 查看镜像标签
docker images your-username/mrt-review-backend

# 删除本地镜像
docker rmi your-username/mrt-review-backend:latest

# 查看推送历史（需要仓库支持）
# 在 Docker Hub 或相应仓库的网页界面查看
```

### 多标签推送

如果需要同时推送多个标签：

```bash
# 构建镜像
docker build -t mrt-review-backend:latest .

# 打多个标签
docker tag mrt-review-backend:latest your-username/mrt-review-backend:latest
docker tag mrt-review-backend:latest your-username/mrt-review-backend:v1.0.0
docker tag mrt-review-backend:latest your-username/mrt-review-backend:stable

# 推送所有标签
docker push your-username/mrt-review-backend:latest
docker push your-username/mrt-review-backend:v1.0.0
docker push your-username/mrt-review-backend:stable
```

## 运行 Docker 容器

### 方式 1: 直接运行

```bash
docker run -d \
  --name mrt-review-backend \
  -p 8000:8000 \
  -e DASHSCOPE_API_KEY=your_api_key_here \
  -v $(pwd)/logs:/app/logs \
  mrt-review-backend:latest
```

### 方式 2: 使用 docker-compose

1. 创建 `.env` 文件（可选）：

```bash
DASHSCOPE_API_KEY=your_api_key_here
QWEN_API_KEY=your_api_key_here
# 或者使用 Azure OpenAI
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
```

2. 运行：

```bash
docker-compose up -d
```

## 环境变量

- `DASHSCOPE_API_KEY`: DashScope (Qwen) API Key
- `QWEN_API_KEY`: Qwen API Key (备用)
- `AZURE_OPENAI_API_KEY`: Azure OpenAI API Key
- `AZURE_OPENAI_ENDPOINT`: Azure OpenAI 端点 URL
- `AZURE_OPENAI_API_VERSION`: Azure OpenAI API 版本（默认: 2024-02-15-preview）
- `MRT_REVIEW_CONFIG`: 配置文件路径（默认: /app/app/config.yaml）

## 验证

访问健康检查端点：

```bash
curl http://localhost:8000/health
```

应该返回：

```json
{"status": "ok"}
```

## 查看日志

```bash
# 查看容器日志
docker logs -f mrt-review-backend

# 或者使用 docker-compose
docker-compose logs -f
```

## 停止和清理

```bash
# 停止容器
docker stop mrt-review-backend

# 删除容器
docker rm mrt-review-backend

# 或者使用 docker-compose
docker-compose down
```

