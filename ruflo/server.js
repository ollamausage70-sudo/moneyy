/**
 * Ruflo MCP Server for AGENT007
 * Starts the Ruflo MCP server with the AGENT007 swarm config.
 * 
 * Deploy as a separate Render web service alongside AGENT007 Flask app.
 */

const path = require('path');
const { spawn } = require('child_process');

const configPath = path.join(__dirname, 'swarm.yaml');
const port = process.env.PORT || 4000;

console.log(`[Ruflo] Starting MCP server with config: ${configPath}`);
console.log(`[Ruflo] Port: ${port}`);

// Start the Ruflo MCP server
const ruflo = spawn('npx', ['@ruvnet/ruflo', 'server', '--config', configPath, '--port', port], {
  stdio: ['pipe', 'inherit', 'inherit'],
  env: { ...process.env },
});

ruflo.on('close', (code) => {
  console.log(`[Ruflo] Process exited with code ${code}`);
  process.exit(code);
});

ruflo.on('error', (err) => {
  console.error(`[Ruflo] Failed to start: ${err.message}`);
  process.exit(1);
});

// Health check endpoint via HTTP
const http = require('http');
const server = http.createServer((req, res) => {
  if (req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'alive', service: 'ruflo-mcp', port }));
  } else {
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end('Ruflo MCP Server for AGENT007');
  }
});

server.listen(port, '0.0.0.0', () => {
  console.log(`[Ruflo] Health endpoint listening on port ${port}`);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  ruflo.kill('SIGTERM');
  process.exit(0);
});
