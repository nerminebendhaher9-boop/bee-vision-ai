const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const cors = require('cors');

const app = express();
const server = http.createServer(app);

const FRONTEND_URL = process.env.FRONTEND_URL || 'http://localhost:8080';

// CORS for Express
app.use(cors({
  origin: FRONTEND_URL,
  credentials: true
}));

// Socket.IO with proper configuration
const io = socketIo(server, {
  cors: {
    origin: FRONTEND_URL,
    credentials: true,
    methods: ["GET", "POST"]
  },
  transports: ['websocket', 'polling']
});

app.use(express.json({ limit: '50mb' }));

// Stub /infer to warn users that the Python backend should be used
app.post('/infer', (req, res) => {
  res.status(503).json({
    error: 'Node.js server does not run inference. Please start the Python backend (python app.py) on port 7000.'
  });
});

// Your other routes here...

io.on('connection', (socket) => {
  console.log('Client connected:', socket.id);
  
  // Send initial data
  socket.emit('connected', { message: 'Connected to backend' });
  
  socket.on('disconnect', () => {
    console.log('Client disconnected:', socket.id);
  });
});

const PORT = process.env.PORT || 7001;
server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});