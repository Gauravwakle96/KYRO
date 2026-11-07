window.ui = SwaggerUIBundle({
  url: '/openapi.json',
  dom_id: '#swagger-ui',
  deepLinking: true,
  validatorUrl: null,
  presets: [SwaggerUIBundle.presets.apis],
  requestInterceptor: async request => {
    request.credentials = 'include'
    if (!['GET', 'HEAD', 'OPTIONS'].includes((request.method ?? 'GET').toUpperCase()) && !request.url.includes('/api/auth/login') && !request.url.includes('/api/auth/register')) {
      const response = await fetch('/api/auth/me', { credentials: 'include' })
      if (response.ok) {
        request.headers ??= {}
        request.headers['X-CSRF-Token'] = (await response.json()).csrf_token
      }
    }
    return request
  },
})
