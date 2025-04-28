<template>
  <div class="privacy-page">
    <!-- 添加logo和动效 -->
    <div class="logo-container animate-fade-in">
      <!-- 中心logo - 不参与3D变换 -->
      <div class="logo-wrapper">
        <img src="@/assets/logo/logo_b.png" alt="ModelVerse Logo" class="page-logo light-logo">
        <img src="@/assets/logo/logo_w.png" alt="ModelVerse Logo" class="page-logo dark-logo">
      </div>
      
      <!-- 太阳系效果 - 单独的3D层 -->
      <div class="solar-system">
        <!-- 轨道和行星 -->
        <div class="orbit orbit-1">
          <div class="planet planet-1"></div>
        </div>
        <div class="orbit orbit-2">
          <div class="planet planet-2"></div>
        </div>
        <div class="orbit orbit-3">
          <div class="planet planet-3"></div>
        </div>
      </div>
    </div>
    
    <div class="page-header animate-fade-in">
      <h1>隐私政策与免责声明</h1>
    </div>
    
    <div class="privacy-content animate-slide-up" style="--delay: 0.3s">
      <section class="policy-section animate-fade-in" style="--delay: 0.4s">
        <h2>资源来源声明</h2>
        <p>本平台所使用的模型和数据集均来自HuggingFace，我们仅提供使用这些资源的技术支持与服务。</p>
      </section>
      
      <section class="policy-section animate-fade-in" style="--delay: 0.5s">
        <h2>用户责任</h2>
        <p>用户需遵守以下规定：</p>
        <ul>
          <li class="animate-slide-right" style="--delay: 0.6s">不得传播、上传或使用任何违法资源</li>
          <li class="animate-slide-right" style="--delay: 0.7s">不得训练违法内容或用于违法用途</li>
          <li class="animate-slide-right" style="--delay: 0.8s">对使用本平台生成的所有内容承担全部责任</li>
        </ul>
      </section>
      
      <section class="policy-section animate-fade-in" style="--delay: 0.9s">
        <h2>免责声明</h2>
        <p>本平台特此声明：</p>
        <ul>
          <li class="animate-slide-right" style="--delay: 1.0s">平台不对任何训练内容或输出内容拥有版权</li>
          <li class="animate-slide-right" style="--delay: 1.1s">平台不对任何训练内容或输出内容拥有所有权</li>
          <li class="animate-slide-right" style="--delay: 1.2s">平台不对用户使用本服务产生的任何后果负责</li>
          <li class="animate-slide-right" style="--delay: 1.3s">用户在使用本平台服务时应自行评估风险并承担责任</li>
        </ul>
      </section>
      
      <section class="policy-section animate-fade-in" style="--delay: 1.4s">
        <h2>服务限制</h2>
        <p>我们保留以下权利：</p>
        <ul>
          <li class="animate-slide-right" style="--delay: 1.5s">随时更改、暂停或终止服务的任何部分</li>
          <li class="animate-slide-right" style="--delay: 1.6s">在发现违规行为时删除相关内容并终止用户访问</li>
          <li class="animate-slide-right" style="--delay: 1.7s">更新本隐私政策与免责声明，变更即时生效</li>
        </ul>
      </section>
      
      <section class="policy-section animate-fade-in" style="--delay: 1.8s">
        <h2>使用须知</h2>
        <p>使用本平台即表示您已阅读、理解并同意遵守上述条款。如不同意，请勿使用本平台的服务。</p>
      </section>
    </div>
  </div>
</template>

<style scoped>
.privacy-page {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

/* Logo和太阳系动效 */
.logo-container {
  text-align: center;
  margin-bottom: 20px;
  height: 150px;
  position: relative;
}

.logo-wrapper {
  position: relative;
  z-index: 10;
  margin-bottom: 0;
}

.page-logo {
  height: 80px;
  width: auto;
  object-fit: contain;
}

/* 默认显示亮色模式logo */
.dark-logo {
  display: none;
}

/* 暗色模式下切换logo */
.dark-theme .light-logo {
  display: none;
}

.dark-theme .dark-logo {
  display: inline-block;
}

/* 备用选择器 */
:root.dark-theme .light-logo {
  display: none !important;
}

:root.dark-theme .dark-logo {
  display: inline-block !important;
}

/* 太阳系效果 */
.solar-system {
  position: absolute;
  width: 160px;
  height: 160px;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%) rotateX(75deg);
  transform-style: preserve-3d;
  perspective: 1000px;
}

/* 轨道 */
.orbit {
  position: absolute;
  top: 50%;
  left: 50%;
  border: 1px solid rgba(var(--primary-rgb, 0, 123, 255), 0.3);
  border-radius: 50%;
  transform-style: preserve-3d;
  animation: orbit-rotation linear infinite;
}

.orbit-1 {
  width: 120px;
  height: 120px;
  margin-top: -60px;
  margin-left: -60px;
  animation-duration: 10s;
  border-color: rgba(var(--primary-rgb, 0, 123, 255), 0.3);
}

.orbit-2 {
  width: 160px;
  height: 160px;
  margin-top: -80px;
  margin-left: -80px;
  animation-duration: 20s;
  border-color: rgba(var(--accent-rgb, 138, 43, 226), 0.3);
}

.orbit-3 {
  width: 200px;
  height: 200px;
  margin-top: -100px;
  margin-left: -100px;
  animation-duration: 30s;
  border-color: rgba(var(--success-rgb, 40, 167, 69), 0.3);
}

/* 行星 */
.planet {
  position: absolute;
  border-radius: 50%;
  transform-style: preserve-3d;
  animation: planet-rotation linear infinite;
}

.planet-1 {
  top: 0;
  left: 50%;
  width: 12px;
  height: 12px;
  margin-left: -6px;
  background: var(--primary, #007bff);
  animation-duration: 10s;
  box-shadow: 0 0 10px var(--primary, #007bff);
}

.planet-2 {
  top: 0;
  left: 50%;
  width: 10px;
  height: 10px;
  margin-left: -5px;
  background: var(--accent, #8a2be2);
  animation-duration: 20s;
  box-shadow: 0 0 10px var(--accent, #8a2be2);
}

.planet-3 {
  top: 0;
  left: 50%;
  width: 8px;
  height: 8px;
  margin-left: -4px;
  background: var(--success, #28a745);
  animation-duration: 30s;
  box-shadow: 0 0 10px var(--success, #28a745);
}

/* 动画定义 */
@keyframes orbit-rotation {
  from {
    transform: rotateZ(0deg);
  }
  to {
    transform: rotateZ(360deg);
  }
}

@keyframes planet-rotation {
  from {
    transform: rotateY(0deg);
  }
  to {
    transform: rotateY(-360deg);
  }
}

.page-header {
  margin-bottom: 24px;
  text-align: center;
}

.page-header h1 {
  font-size: 28px;
  margin-bottom: 8px;
  /* 使用CSS变量实现明暗模式适配的渐变效果 */
  background: linear-gradient(90deg, var(--primary, #007bff) 0%, var(--accent, #8a2be2) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  display: inline-block;
  transition: background 0.3s ease;
}

/* 暗色模式下标题的特殊渐变效果 */
.dark-theme .page-header h1 {
  background: linear-gradient(90deg, var(--primary, #5c9eff) 0%, var(--accent, #b985ff) 100%);
  -webkit-background-clip: text;
  background-clip: text;
}

/* 备用选择器，确保能捕获暗色主题 */
:root.dark-theme .page-header h1 {
  background: linear-gradient(90deg, var(--primary, #5c9eff) 0%, var(--accent, #b985ff) 100%);
  -webkit-background-clip: text;
  background-clip: text;
}

.privacy-content {
  background-color: var(--bg-card);
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  padding: 24px;
  transition: background-color 0.3s ease, box-shadow 0.3s ease;
}

.dark-theme .privacy-content {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3);
  border: 1px solid var(--border);
}

.policy-section {
  margin-bottom: 24px;
  transition: transform 0.3s ease;
}

.policy-section:hover {
  transform: translateY(-5px);
}

.policy-section:last-child {
  margin-bottom: 0;
}

.policy-section h2 {
  font-size: 20px;
  margin-bottom: 16px;
  color: var(--primary);
  border-bottom: 1px solid var(--border);
  padding-bottom: 8px;
  transition: color 0.3s ease, border-color 0.3s ease;
}

.policy-section p {
  margin-bottom: 16px;
  line-height: 1.6;
  color: var(--text-primary);
  transition: color 0.3s ease;
}

.policy-section ul {
  padding-left: 24px;
  margin-bottom: 16px;
}

.policy-section li {
  margin-bottom: 8px;
  line-height: 1.6;
  color: var(--text-primary);
  transition: transform 0.3s ease, color 0.3s ease;
}

.policy-section li:hover {
  transform: translateX(10px);
}

/* 动画效果 */
.animate-fade-in {
  animation: fadeIn 1s ease-out forwards;
  animation-delay: var(--delay, 0s);
  opacity: 0;
}

.animate-slide-up {
  animation: slideUp 0.8s ease-out forwards;
  animation-delay: var(--delay, 0s);
  opacity: 0;
  transform: translateY(30px);
}

.animate-slide-right {
  animation: slideRight 0.8s ease-out forwards;
  animation-delay: var(--delay, 0s);
  opacity: 0;
  transform: translateX(-30px);
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes slideRight {
  from {
    opacity: 0;
    transform: translateX(-30px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}
</style> 