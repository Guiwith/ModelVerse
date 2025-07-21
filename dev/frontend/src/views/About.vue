<template>
  <div class="about-page">
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
      <h1>关于我们</h1>
      <p class="subtitle">ModelVerse - 您的AI模型训练与推理平台</p>
    </div>

    <div class="about-content">
      <section class="about-section animate-slide-up" style="--delay: 0.1s">
        <h2>平台简介</h2>
        <p>ModelVerse致力于为个人开发者和企业提供易用、高效的模型训练与推理平台。我们的目标是降低AI应用开发的门槛，让更多人能够轻松地利用人工智能技术创造价值。</p>
      </section>
      
      <section class="about-section animate-slide-up" style="--delay: 0.2s">
        <h2>我们的使命</h2>
        <p>让AI技术更加普及，使每一位开发者都能轻松使用和定制AI模型，为各行各业带来智能化升级。</p>
      </section>
      
      <section class="about-section animate-slide-up" style="--delay: 0.3s">
        <h2>技术优势</h2>
        <ul class="feature-list">
          <li class="animate-slide-right" style="--delay: 0.4s"><span class="material-icons">check_circle</span> 一站式模型训练与推理平台</li>
          <li class="animate-slide-right" style="--delay: 0.5s"><span class="material-icons">check_circle</span> 支持主流开源模型的快速部署</li>
          <li class="animate-slide-right" style="--delay: 0.6s"><span class="material-icons">check_circle</span> 高效的推理管理系统</li>
          <li class="animate-slide-right" style="--delay: 0.7s"><span class="material-icons">check_circle</span> 用户友好的界面设计</li>
          <li class="animate-slide-right" style="--delay: 0.8s"><span class="material-icons">check_circle</span> 便捷的模型评估工具</li>
        </ul>
      </section>
      
      <section class="about-section animate-slide-up" style="--delay: 0.9s">
        <h2>联系我们</h2>
        <p>如有任何问题或合作意向，请联系我们</p>
        
        <div class="contact-info">
          <div class="contact-item animate-fade-in" style="--delay: 1s">
            <span class="material-icons">email</span>
            <p>ModelVerse</p>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.about-page {
  max-width: 1000px;
  margin: 0 auto;
  padding: 20px;
}

.logo-container {
  text-align: center;
  margin-bottom: 20px;
  height: 150px;
  position: relative;
}

/* Logo独立层 */
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

/* 如果上面的选择器不起作用，尝试这种写法 */
:root.dark-theme .light-logo {
  display: none !important;
}

:root.dark-theme .dark-logo {
  display: inline-block !important;
}

.page-header {
  margin-bottom: 24px;
  text-align: center;
}

.page-header h1 {
  font-size: 32px;
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

.page-header .subtitle {
  font-size: 18px;
  color: var(--text-secondary);
}

.about-content {
  background-color: var(--bg-card);
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  padding: 24px;
  transition: background-color 0.3s ease, box-shadow 0.3s ease;
}

.dark-theme .about-content {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3);
  border: 1px solid var(--border);
}

.about-section {
  margin-bottom: 32px;
  transition: transform 0.3s ease;
}

.about-section:hover {
  transform: translateY(-5px);
}

.about-section:last-child {
  margin-bottom: 0;
}

.about-section h2 {
  font-size: 24px;
  margin-bottom: 16px;
  color: var(--primary);
  border-bottom: 1px solid var(--border);
  padding-bottom: 8px;
  transition: color 0.3s ease, border-color 0.3s ease;
}

.about-section p {
  margin-bottom: 16px;
  line-height: 1.6;
  transition: color 0.3s ease;
  color: var(--text-primary);
}

.team-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 24px;
  margin-top: 24px;
}

.team-member {
  background-color: var(--bg-secondary);
  border-radius: 8px;
  padding: 20px;
  text-align: center;
  transition: transform 0.3s ease, box-shadow 0.3s ease, background-color 0.3s ease;
}

.team-member:hover {
  transform: translateY(-4px);
  box-shadow: 0 6px 12px rgba(0, 0, 0, 0.1);
}

.dark-theme .team-member:hover {
  box-shadow: 0 6px 12px rgba(0, 0, 0, 0.3);
}

.member-avatar {
  width: 80px;
  height: 80px;
  background-color: var(--primary-light);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
  transition: background-color 0.3s ease;
}

.member-avatar .material-icons {
  font-size: 40px;
  color: var(--primary);
  transition: color 0.3s ease;
}

.team-member h3 {
  margin-bottom: 8px;
  font-size: 18px;
  color: var(--text-primary);
  transition: color 0.3s ease;
}

.member-title {
  color: var(--primary);
  font-weight: 600;
  margin-bottom: 8px;
  transition: color 0.3s ease;
}

.member-bio {
  font-size: 14px;
  line-height: 1.5;
  color: var(--text-secondary);
  transition: color 0.3s ease;
}

.feature-list {
  list-style: none;
  padding: 0;
}

.feature-list li {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
  transition: transform 0.3s ease;
  color: var(--text-primary);
}

.feature-list li:hover {
  transform: translateX(10px);
}

.feature-list .material-icons {
  color: var(--success);
  margin-right: 12px;
  font-size: 20px;
  transition: color 0.3s ease, transform 0.3s ease;
}

.feature-list li:hover .material-icons {
  transform: scale(1.2);
}

.contact-info {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
  margin-top: 16px;
}

.contact-item {
  display: flex;
  align-items: center;
  background-color: var(--bg-secondary);
  padding: 12px;
  border-radius: 6px;
  transition: background-color 0.3s ease, transform 0.3s ease, box-shadow 0.3s ease;
}

.contact-item:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

.dark-theme .contact-item:hover {
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
}

.contact-item .material-icons {
  margin-right: 12px;
  color: var(--primary);
  transition: color 0.3s ease, transform 0.3s ease;
}

.contact-item:hover .material-icons {
  transform: scale(1.2);
}

.contact-item p {
  margin: 0;
  color: var(--text-primary);
  transition: color 0.3s ease;
}

@media (max-width: 768px) {
  .team-grid {
    grid-template-columns: 1fr;
  }
  
  .contact-info {
    grid-template-columns: 1fr;
  }
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