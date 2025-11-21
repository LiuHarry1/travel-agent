# 快速解决 Docker 构建超时问题

## ⚡ 立即执行（推荐）

运行以下脚本自动配置：

```bash
./fix_docker_network.sh
```

然后重新尝试：

```bash
docker pull python:3.11-slim
docker build -t mrt-review-backend:latest .
```

## 🚀 手动配置：Docker 镜像加速器

### macOS (Docker Desktop)

1. **打开 Docker Desktop**
2. **点击右上角设置图标（齿轮）**
3. **选择 "Docker Engine"**
4. **在 JSON 配置中添加以下内容**：

```json
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com"
  ]
}
```

5. **点击 "Apply & Restart"**
6. **等待 Docker 重启完成（约 30 秒）**

### 验证配置

重启后，运行以下命令验证：

```bash
docker info | grep -A 5 "Registry Mirrors"
```

如果看到你配置的镜像地址，说明配置成功。

### 重新构建

```bash
docker build -t mrt-review-backend:latest .
```

## 🔄 临时解决方案：手动拉取镜像

### 使用自动重试脚本

```bash
# 带自动重试的拉取脚本
./pull_base_image.sh
```

### 手动拉取（带重试）

```bash
# 方法 1: 使用代理（如果有）
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
docker pull python:3.11-slim

# 方法 2: 多次重试（网络不稳定时）
for i in {1..5}; do
  echo "尝试 $i/5..."
  docker pull python:3.11-slim && break || sleep 5
done

# 拉取成功后，正常构建
docker build -t mrt-review-backend:latest .
```

### 使用代理（如果已配置）

```bash
# 设置代理（根据你的代理配置修改）
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890

# 拉取镜像
docker pull python:3.11-slim

# 构建
docker build -t mrt-review-backend:latest .
```

## 📝 完整步骤示例

```bash
# 1. 配置镜像加速器（在 Docker Desktop 中，见上方说明）

# 2. 验证配置
docker info | grep "Registry Mirrors"

# 3. 构建镜像
cd backend
docker build -t mrt-review-backend:latest .

# 4. 验证构建成功
docker images | grep mrt-review-backend
```

