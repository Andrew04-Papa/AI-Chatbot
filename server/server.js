const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const axios = require('axios');

const app = express();
const PORT = 3001;

// Middleware
app.use(cors());
app.use(bodyParser.json());

// ✅ API chatbot - gửi sang Flask embedding
app.post('/api/chat', async (req, res) => {
  const { userInput } = req.body;

  try {
    const response = await axios.post('http://127.0.0.1:5000/embed', {
      question: userInput
    });

    const reply = response.data.reply || "❌ Không có phản hồi từ hệ thống.";
    res.json({ reply });
  } catch (error) {
    console.error('❌ Lỗi kết nối đến API Python:', error.message);
    res.status(500).json({ reply: '⚠️ Không thể kết nối tới hệ thống phân tích ngữ nghĩa.' });
  }
});

app.listen(PORT, () => {
  console.log(`✅ Node.js server đang chạy tại http://localhost:${PORT}`);
});
