<template>
  <div class="privacy-page">
    <div class="page-header">
      <h1>隐私政策与免责声明</h1>
    </div>
    
    <div class="privacy-content">
      <section class="policy-section">
        <h2>资源来源声明</h2>
        <p>本平台所使用的模型和数据集均来自HuggingFace，我们仅提供使用这些资源的技术支持与服务。</p>
      </section>
      
      <section class="policy-section">
        <h2>用户责任</h2>
        <p>用户需遵守以下规定：</p>
        <ul>
          <li>不得传播、上传或使用任何违法资源</li>
          <li>不得训练违法内容或用于违法用途</li>
          <li>对使用本平台生成的所有内容承担全部责任</li>
        </ul>
      </section>
      
      <section class="policy-section">
        <h2>免责声明</h2>
        <p>本平台特此声明：</p>
        <ul>
          <li>平台不对任何训练内容或输出内容拥有版权</li>
          <li>平台不对任何训练内容或输出内容拥有所有权</li>
          <li>平台不对用户使用本服务产生的任何后果负责</li>
          <li>用户在使用本平台服务时应自行评估风险并承担责任</li>
        </ul>
      </section>
      
      <section class="policy-section">
        <h2>服务限制</h2>
        <p>我们保留以下权利：</p>
        <ul>
          <li>随时更改、暂停或终止服务的任何部分</li>
          <li>在发现违规行为时删除相关内容并终止用户访问</li>
          <li>更新本隐私政策与免责声明，变更即时生效</li>
        </ul>
      </section>
      
      <section class="policy-section">
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

.page-header {
  margin-bottom: 32px;
  text-align: center;
}

.page-header h1 {
  font-size: 28px;
  margin-bottom: 8px;
}

.privacy-content {
  background-color: var(--bg-card);
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  padding: 24px;
}

.policy-section {
  margin-bottom: 24px;
}

.policy-section:last-child {
  margin-bottom: 0;
}

.policy-section h2 {
  font-size: 20px;
  margin-bottom: 16px;
  color: var(--primary);
}

.policy-section p {
  margin-bottom: 16px;
  line-height: 1.6;
}

.policy-section ul {
  padding-left: 24px;
  margin-bottom: 16px;
}

.policy-section li {
  margin-bottom: 8px;
  line-height: 1.6;
}
</style> 