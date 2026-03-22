<template>
  <div class="not-found">
    <h1>404</h1>
    <p>Page not found</p>
    <router-link to="/">Back to Home</router-link>
  </div>
</template>

<script setup>
</script>

<style scoped>
.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  font-family: 'Inter', sans-serif;
  color: #EAEAEA;
  background: #0a0a0a;
}
.not-found h1 {
  font-size: 6rem;
  margin: 0;
  font-weight: 700;
  background: linear-gradient(135deg, #667eea, #764ba2);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.not-found p {
  font-size: 1.5rem;
  margin: 1rem 0 2rem;
  color: #888;
}
.not-found a {
  color: #667eea;
  text-decoration: none;
  font-size: 1.1rem;
}
.not-found a:hover {
  text-decoration: underline;
}
</style>
