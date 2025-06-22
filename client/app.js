let pendingDeleteIndex = null

// Cải thiện conversation context với session management
const conversationContext = {
  sessionId: null,
  lastFile: null,
  lastSection: null,
  conversationHistory: [],
}

// Khởi tạo session khi load trang
async function initializeSession() {
  try {
    const response = await fetch("http://localhost:5000/conversation-history", {
      credentials: "include",
    })
    const data = await response.json()
    conversationContext.sessionId = data.session_id
    conversationContext.conversationHistory = data.history || []

    // Load lại lịch sử chat nếu có
    loadChatHistory()
    console.log("Session initialized:", conversationContext.sessionId)
  } catch (error) {
    console.error("Lỗi khởi tạo session:", error)
  }
}

function loadChatHistory() {
  const chatBody = document.getElementById("chat-body")

  // Xóa tin nhắn chào mừng cũ
  chatBody.innerHTML = ""

  // Thêm tin nhắn chào mừng
  const welcomeDiv = document.createElement("div")
  welcomeDiv.className = "msg-row bot"
  welcomeDiv.innerHTML = `
    <img src="./assets/img/bot.jpg" class="msg-avatar" alt="bot">
    <div class="msg-bubble">Xin chào! Tôi có thể giúp gì cho bạn?</div>
  `
  chatBody.appendChild(welcomeDiv)

  // Load lịch sử từ server - kiểm tra dữ liệu trước khi hiển thị
  if (conversationContext.conversationHistory && conversationContext.conversationHistory.length > 0) {
    conversationContext.conversationHistory.forEach((item) => {
      // Kiểm tra dữ liệu hợp lệ
      if (!item.user_message || !item.bot_response) {
        return // Skip invalid items
      }

      // Thêm tin nhắn user
      const userDiv = document.createElement("div")
      userDiv.className = "msg-row user"
      userDiv.innerHTML = `
        <div class="msg-bubble">${item.user_message}</div>
        <img src="./assets/img/user.webp" class="msg-avatar" alt="user">
      `
      chatBody.appendChild(userDiv)

      // Thêm tin nhắn bot
      const botDiv = document.createElement("div")
      botDiv.className = "msg-row bot"

      if (item.response_type === "file") {
        // Hiển thị file attachment với layout dọc
        const fileBlock = `<div style="display: flex; flex-direction: column; align-items: flex-start;">
  <div style="display: flex; align-items: center; gap: 4px;">
    <span style="font-size: 20px; color: #6c757d;">📄</span>
    <span style="font-weight: bold; font-size: 14px; color: #495057;">Tệp đính kèm</span>
  </div>
  <a href="http://localhost:5000/files/${item.file_referenced}" target="_blank" style="color: #7a1ea1; text-decoration: none; font-size: 15px; font-weight: 500; word-break: break-all; line-height: 1.1; margin-top: -2px;">${item.file_referenced}</a>
</div>`

        botDiv.innerHTML = `
          <img src="./assets/img/bot.jpg" class="msg-avatar" alt="bot">
          <div class="msg-bubble">${fileBlock}</div>
        `
      } else {
        botDiv.innerHTML = `
          <img src="./assets/img/bot.jpg" class="msg-avatar" alt="bot">
          <div class="msg-bubble">${item.bot_response}</div>
        `
      }

      chatBody.appendChild(botDiv)

      // Cập nhật context nếu có file
      if (item.file_referenced) {
        conversationContext.lastFile = item.file_referenced
      }
    })
  }

  chatBody.scrollTop = chatBody.scrollHeight
}

function toggleChat() {
  const box = document.getElementById("chatbot-box")
  box.classList.toggle("hidden")
}

document.addEventListener("DOMContentLoaded", () => {
  // Khởi tạo session trước
  initializeSession()

  loadQA()

  document.getElementById("close-add-qna").onclick = toggleAddQnaModal

  document.getElementById("qaForm").addEventListener("submit", async (e) => {
    e.preventDefault()
    const questions = document.getElementById("new-questions").value.trim().split("\n").filter(Boolean)
    const answer = document.getElementById("new-answer").value.trim()

    const fileInput = document.getElementById("new-file")
    const file = fileInput.files[0]?.name || null

    // ✅ Kiểm tra có ít nhất 1 trong 2: answer hoặc file
    if (!answer && !file) {
      showToast("❌ Phải có ít nhất câu trả lời HOẶC file đính kèm!")
      return
    }

    const resQA = await fetch("http://localhost:5000/qa-list")
    const qaList = await resQA.json()

    // ✅ Sửa logic kiểm tra duplicate - chỉ kiểm tra khi không phải đang edit
    if (!isEditing) {
      const isDuplicateQuestion = qaList.some((item) => questions.some((q) => item.questions.includes(q)))

      // ✅ Chỉ kiểm tra duplicate answer khi có answer
      const isDuplicateAnswer = answer && qaList.some((item) => item.answer && item.answer.trim() === answer)

      // ✅ Chỉ kiểm tra duplicate file khi có file
      const isDuplicateFile = file && qaList.some((item) => item.answer_file === file)

      if (isDuplicateQuestion || isDuplicateAnswer || isDuplicateFile) {
        let duplicateType = ""
        if (isDuplicateQuestion) duplicateType += "❗ Câu hỏi đã tồn tại.\n"
        if (isDuplicateAnswer) duplicateType += "❗ Câu trả lời đã tồn tại.\n"
        if (isDuplicateFile) duplicateType += "❗ File đính kèm đã tồn tại."

        showToast(duplicateType.trim())
        return
      }
    }

    const formData = new FormData()
    questions.forEach((q) => formData.append("questions[]", q))
    formData.append("answer", answer) // Có thể là empty string
    if (fileInput.files[0]) {
      formData.append("file", fileInput.files[0])
    }

    const url = isEditing ? `http://localhost:5000/qa-update/${editingIndex}` : "http://localhost:5000/qa-add"

    const method = "POST"

    try {
      const res = await fetch(url, {
        method,
        body: formData,
      })

      const data = await res.json()

      if (data.message === "success") {
        const toastMsg = isEditing ? "✏️ Đã cập nhật Q&A thành công!" : "✅ Đã thêm Q&A mới!"

        showToast(toastMsg)

        setTimeout(() => {
          toggleAddQnaModal()
          document.getElementById("qaForm").reset()
          isEditing = false
          editingIndex = null
          loadQA()
        }, 300)
      } else {
        showToast("❌ Lưu thất bại: " + (data.message || "Lỗi không xác định"))
      }
    } catch (err) {
      showToast("⚠️ Không kết nối được tới máy chủ.")
    }
  })
})

function sendMessage() {
  const input = document.getElementById("user-input")
  const message = input.value.trim()
  if (!message) return

  const chatBody = document.getElementById("chat-body")

  // Lưu vào lịch sử cuộc trò chuyện local
  conversationContext.conversationHistory.push({
    type: "user",
    message: message,
    timestamp: new Date(),
  })

  // Tạo khối chung cho user + bot
  const msgWrapper = document.createElement("div")
  msgWrapper.className = "message-wrapper"
  chatBody.appendChild(msgWrapper)

  // Tạo và thêm tin nhắn người dùng
  const userDiv = document.createElement("div")
  userDiv.className = "msg-row user"
  userDiv.innerHTML = `
        <div class="msg-bubble">${message}</div>
        <img src="./assets/img/user.webp" class="msg-avatar" alt="user">
  `
  msgWrapper.appendChild(userDiv)

  // Tạo và thêm tin nhắn bot (đang trả lời)
  const botDiv = document.createElement("div")
  botDiv.className = "msg-row bot"
  botDiv.innerHTML = `
    <img src="./assets/img/bot.jpg" class="msg-avatar" alt="bot">
    <div class="msg-bubble">Đang trả lời...</div>
  `
  msgWrapper.appendChild(botDiv)

  input.value = ""
  chatBody.scrollTop = chatBody.scrollHeight

  // Gọi AI xử lý và thay nội dung
  sendMessageToOllama(message).then((reply) => {
    chatBody.scrollTop = chatBody.scrollHeight

    // Lưu phản hồi vào lịch sử local
    conversationContext.conversationHistory.push({
      type: "bot",
      message: reply,
      timestamp: new Date(),
    })

    // Update conversation context if the reply contains a file
    if (reply.includes('href="/files/')) {
      const fileMatch = reply.match(/href="\/files\/([^"]+)"/)
      if (fileMatch && fileMatch[1]) {
        conversationContext.lastFile = fileMatch[1]
        console.log("Set context to file:", conversationContext.lastFile)
      }
    }

    // Nếu là khối HTML (file đính kèm), thì thay toàn bộ bubble
    if (reply.startsWith("<div")) {
      botDiv.innerHTML = `
        <img src="./assets/img/bot.jpg" class="msg-avatar" alt="bot">
        <div class="msg-bubble">${reply}</div>
      `
    } else {
      botDiv.querySelector(".msg-bubble").innerHTML = reply
    }
  })
}

// Cải thiện hàm gửi tin nhắn với context tốt hơn
function sendMessageToOllama(promptText) {
  const payload = {
    question: promptText,
    use: "auto",
  }

  // Thêm context từ cuộc trò chuyện
  if (conversationContext.sessionId) {
    payload.context = {
      sessionId: conversationContext.sessionId,
      lastFile: conversationContext.lastFile,
      lastSection: conversationContext.lastSection,
      conversationHistory: conversationContext.conversationHistory.slice(-5), // 5 tin nhắn gần nhất
    }
  }

  return fetch("http://localhost:5000/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    credentials: "include", // Quan trọng để duy trì session
  })
    .then((res) => res.json())
    .then((data) => {
      // Trường hợp trả về file đính kèm - sử dụng layout dọc
      if (data && data.answer_file) {
        const fileName = data.answer_file
        conversationContext.lastFile = fileName

        // File attachment với layout dọc
        const fileBlock = `<div style="display: flex; flex-direction: column; align-items: flex-start;">
  <div style="display: flex; align-items: center; gap: 4px;">
    <span style="font-size: 20px; color: #6c757d;">📄</span>
    <span style="font-weight: bold; font-size: 14px; color: #495057;">Tệp đính kèm</span>
  </div>
  <a href="http://localhost:5000/files/${fileName}" target="_blank" style="color: #7a1ea1; text-decoration: none; font-size: 15px; font-weight: 500; word-break: break-all; line-height: 1.1; margin-top: -2px;" title="${fileName}">
    ${fileName}
  </a>
</div>`
        return fileBlock
      }

      // Trường hợp trả về nội dung hoặc HTML formatted
      if (data && data.answer) {
        // Update context if the reply contains a file reference
        if (data.answer.includes("file-content-wrapper") || data.answer.includes("Trích từ file")) {
          const fileMatch = data.answer.match(/Trích từ file[:\s]*([^<\n]+)/)
          if (fileMatch && fileMatch[1]) {
            conversationContext.lastFile = fileMatch[1].trim()
            console.log("Set context to file:", conversationContext.lastFile)
          }
        }
        return data.answer
      }

      return "❌ Không có phản hồi"
    })
    .catch((err) => "❌ Không tìm thấy kết quả phù hợp")
}

// Thêm nút xóa lịch sử chat
async function clearChatHistory() {
  if (confirm("Bạn có chắc muốn xóa toàn bộ lịch sử chat?")) {
    try {
      // Gọi API để xóa database
      const response = await fetch("http://localhost:5000/clear-chat", {
        method: "POST",
        credentials: "include",
      })

      const data = await response.json()

      if (data.message === "success") {
        // Reset conversation context
        conversationContext.conversationHistory = []
        conversationContext.lastFile = null
        conversationContext.lastSection = null

        // Reset UI
        const chatBody = document.getElementById("chat-body")
        chatBody.innerHTML = `
          <div class="msg-row bot">
            <img src="./assets/img/bot.jpg" class="msg-avatar" alt="bot">
            <div class="msg-bubble">Xin chào! Tôi có thể giúp gì cho bạn?</div>
          </div>
        `

        showToast("🗑️ Đã xóa lịch sử chat!")
      } else {
        showToast("❌ Lỗi khi xóa lịch sử chat!")
      }
    } catch (error) {
      console.error("Error clearing chat:", error)
      showToast("❌ Không thể xóa lịch sử chat!")
    }
  }
}

// Các hàm khác giữ nguyên...
async function loadQA() {
  const res = await fetch("http://localhost:5000/qa-list")
  const qaList = await res.json()
  const tbody = document.querySelector("#qa-table tbody")
  tbody.innerHTML = ""

  qaList.forEach((item, index) => {
    const tr = document.createElement("tr")
    const fileLink = item.answer_file ? `http://localhost:5000/files/${item.answer_file}` : ""
    tr.innerHTML = `
      <td class="center">${index + 1}</td>
      <td class="left">${item.questions[0]}</td>
      <td class="left">${item.answer || ""}</td>
      <td class="file">
        ${
          fileLink
            ? `<a href="${fileLink}" target="_blank" style="color: #007bff; text-decoration: underline;">
          <i class="fas fa-file-alt"></i> Tài liệu
        </a>`
            : ""
        }
      </td>

      <td>
        <div class="action-buttons">
          <button onclick="editQA(${index})"><i class="fas fa-pen"></i> Sửa</button>
          <button onclick="deleteQA(${index})"><i class="fas fa-trash"></i> Xoá</button>
          <button onclick="openAddQnaForm()"><i class="fas fa-plus"></i> Thêm</button>
        </div>
      </td>
    `
    tbody.appendChild(tr)
  })
}

function deleteQA(index) {
  pendingDeleteIndex = index
  document.getElementById("confirm-modal").classList.remove("hidden")
}

let isEditing = false
let editingIndex = null

async function editQA(index) {
  const res = await fetch("http://localhost:5000/qa-list")
  const data = await res.json()
  const qa = data[index]

  document.getElementById("new-questions").value = qa.questions.join("\n")
  document.getElementById("new-answer").value = qa.answer || ""
  const fileInput = document.getElementById("new-file")
  const newFileInput = fileInput.cloneNode(true)
  fileInput.parentNode.replaceChild(newFileInput, fileInput)

  isEditing = true
  editingIndex = index

  document.querySelector(".modal-title").innerHTML = '<i class="fas fa-pen"></i> Sửa Q&A'

  toggleAddQnaModal()
}

function toggleQASection(forceShow = null) {
  const wrapper = document.getElementById("qa-wrapper")
  const toggleBtn = document.getElementById("toggle-qa-btn")

  const willShow = forceShow !== null ? forceShow : wrapper.classList.contains("hidden")

  wrapper.classList.toggle("hidden", !willShow)
  if (willShow) {
    toggleBtn.style.display = "none"
  } else {
    toggleBtn.style.display = "block"
    toggleBtn.style.margin = "20px auto"
  }
}

function toggleAddQnaModal() {
  const modal = document.getElementById("add-qna-modal")
  modal.classList.toggle("hidden")
}

document.getElementById("user-input").addEventListener("keypress", (e) => {
  if (e.key === "Enter") {
    e.preventDefault()
    sendMessage()
  }
})

function showToast(msg) {
  const toast = document.getElementById("toast-message")
  toast.innerHTML = msg
  toast.classList.add("show")

  setTimeout(() => {
    toast.classList.remove("show")
  }, 2500)
}

document.getElementById("confirm-ok").onclick = async () => {
  if (pendingDeleteIndex !== null) {
    await fetch(`http://localhost:5000/qa-delete/${pendingDeleteIndex}`, { method: "DELETE" })
    loadQA()
    showToast('<i class="fas fa-trash"></i> Đã xoá Q&A thành công!')
    pendingDeleteIndex = null
    document.getElementById("confirm-modal").classList.add("hidden")
  }
}

document.getElementById("confirm-cancel").onclick = () => {
  pendingDeleteIndex = null
  document.getElementById("confirm-modal").classList.add("hidden")
}

function openAddQnaForm() {
  isEditing = false
  editingIndex = null
  document.getElementById("qaForm").reset()
  document.querySelector(".modal-title").innerHTML = '<i class="fas fa-plus"></i> Thêm Q&A'
  toggleAddQnaModal()
}
