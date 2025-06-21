let pendingDeleteIndex = null

// Cải thiện conversation context
const conversationContext = {
  lastFile: null,
  lastSection: null,
  conversationHistory: [],
}

function toggleChat() {
  const box = document.getElementById("chatbot-box")
  box.classList.toggle("hidden")
}

document.addEventListener("DOMContentLoaded", () => {
  loadQA()

  document.getElementById("close-add-qna").onclick = toggleAddQnaModal

  document.getElementById("qaForm").addEventListener("submit", async (e) => {
    e.preventDefault()
    const questions = document.getElementById("new-questions").value.trim().split("\n").filter(Boolean)
    const answer = document.getElementById("new-answer").value.trim()

    const fileInput = document.getElementById("new-file")
    const file = fileInput.files[0]?.name || null

    const resQA = await fetch("http://localhost:5000/qa-list")
    const qaList = await resQA.json()

    const isDuplicate = qaList.some(
      (item) =>
        questions.some((q) => item.questions.includes(q)) ||
        item.answer === answer ||
        (file && item.answer_file === file),
    )

    if (isDuplicate && !isEditing) {
      let duplicateType = ""

      const isDuplicateQuestion = qaList.some((item) => questions.some((q) => item.questions.includes(q)))

      const isDuplicateAnswer = qaList.some((item) => item.answer === answer)
      const isDuplicateFile = qaList.some((item) => file && item.answer_file === file)

      if ((isDuplicateQuestion || isDuplicateAnswer || isDuplicateFile) && !isEditing) {
        if (isDuplicateQuestion) duplicateType += "❗ Câu hỏi đã tồn tại.\n"
        if (isDuplicateAnswer) duplicateType += "❗ Câu trả lời đã tồn tại.\n"
        if (isDuplicateFile) duplicateType += "❗ File đính kèm đã tồn tại."

        showToast(duplicateType.trim())
        return
      }

      return
    }

    const formData = new FormData()
    questions.forEach((q) => formData.append("questions[]", q))
    formData.append("answer", answer)
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

      if (data.message) {
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
        showToast("❌ Lưu thất bại.")
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

  // Lưu vào lịch sử cuộc trò chuyện
  conversationContext.conversationHistory.push({
    type: "user",
    message: message,
    timestamp: new Date(),
  })

  //  Tạo khối chung cho user + bot
  const msgWrapper = document.createElement("div")
  msgWrapper.className = "message-wrapper"
  chatBody.appendChild(msgWrapper)

  // 👉 Tạo và thêm tin nhắn người dùng
  const userDiv = document.createElement("div")
  userDiv.className = "msg-row user"
  userDiv.innerHTML = `
        <div class="msg-bubble">${message}</div>
        <img src="./assets/img/user.webp" class="msg-avatar" alt="user">
  `
  msgWrapper.appendChild(userDiv)

  // 👉 Tạo và thêm tin nhắn bot (đang trả lời)
  const botDiv = document.createElement("div")
  botDiv.className = "msg-row bot"
  botDiv.innerHTML = `
    <img src="./assets/img/bot.jpg" class="msg-avatar" alt="bot">
    <div class="msg-bubble">Đang trả lời...</div>
  `
  msgWrapper.appendChild(botDiv)

  input.value = ""
  chatBody.scrollTop = chatBody.scrollHeight

  // 👉 Gọi AI xử lý và thay nội dung
  sendMessageToOllama(message).then((reply) => {
    chatBody.scrollTop = chatBody.scrollHeight

    // Lưu phản hồi vào lịch sử
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

function toggleAddQna() {
  const box = document.getElementById("add-qna-box")
  box.classList.toggle("hidden")
}

function previewQna() {
  const questions = document
    .getElementById("new-questions")
    .value.trim()
    .split("\n")
    .filter((q) => q)
  const answer = document.getElementById("new-answer").value.trim()
  const fileInput = document.getElementById("new-file")
  const file = fileInput.files[0]

  if (questions.length === 0) {
    alert("Vui lòng nhập ít nhất 1 câu hỏi")
    return
  }

  const obj = { questions }
  if (answer) obj.answer = answer
  if (file) obj.answer_file = file.name

  document.getElementById("qna-preview").textContent = JSON.stringify(obj, null, 2)
}

// Cải thiện hàm gửi tin nhắn với context tốt hơn
function sendMessageToOllama(promptText) {
  const payload = {
    question: promptText,
    use: "auto",
  }

  // Thêm context từ cuộc trò chuyện
  if (conversationContext.lastFile) {
    payload.context = {
      lastFile: conversationContext.lastFile,
      lastSection: conversationContext.lastSection,
      conversationHistory: conversationContext.conversationHistory.slice(-5), // 5 tin nhắn gần nhất
    }
  }

  return fetch("http://localhost:5000/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
    .then((res) => res.json())
    .then((data) => {
      // Trường hợp trả về file đính kèm
      if (data && data.answer_file) {
        const fileName = data.answer_file
        conversationContext.lastFile = fileName

        const fileBlock = `
    <div>
      <div style="display: flex; align-items: center;">
        <span style="font-size: 18px;">📄</span>
        <span style="font-weight: bold; color: #495057;">Tệp đính kèm:</span>
      </div>
      <div style="margin-left: 4px;">
        <a href="http://localhost:5000/files/${fileName}" target="_blank"
          style="color: #7a1ea1; text-decoration: none; font-weight: 500;">
          ${fileName}
        </a>
      </div>
    </div>
  `
        return fileBlock
      }

      // Trường hợp trả về nội dung
      if (data && data.answer) {
        // Update context if the reply contains a file reference
        if (data.answer.includes("Trích từ file")) {
          const fileMatch = data.answer.match(/Trích từ file <u>([^<]+)<\/u>/)
          if (fileMatch && fileMatch[1]) {
            conversationContext.lastFile = fileMatch[1]
            console.log("Set context to file:", conversationContext.lastFile)
          }
        }
        return data.answer
      }

      return "❌ Không có phản hồi"
    })
    .catch((err) => "❌ Không tìm thấy kết quả phù hợp")
}

// ✅ Làm sạch emoji và ký tự ngoài tiếng Việt
function cleanVietnameseResponse(text) {
  return text.replace(/[^\p{L}\p{N}\p{P}\p{Zs}]/gu, "")
}

// ✅ Load bảng Q&A với nút "Thêm" trong mỗi dòng
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

// ✅ Thêm chức năng toggle phần quản lý Q&A
function toggleQASection(forceShow = null) {
  const wrapper = document.getElementById("qa-wrapper")
  const toggleBtn = document.getElementById("toggle-qa-btn")

  // Tự xác định trạng thái nếu chưa truyền vào
  const willShow = forceShow !== null ? forceShow : wrapper.classList.contains("hidden")

  // Cập nhật hiển thị
  wrapper.classList.toggle("hidden", !willShow)
  // ✅ Ẩn/hiện nút và giữ căn giữa
  if (willShow) {
    toggleBtn.style.display = "none"
  } else {
    toggleBtn.style.display = "block"
    toggleBtn.style.margin = "20px auto"
  }
}

// ✅ Toggle hiển thị form Thêm Q&A
function toggleAddQnaModal() {
  const modal = document.getElementById("add-qna-modal")
  modal.classList.toggle("hidden")
}

// ✅ Cho phép bấm Enter để gửi trong ô nhập chatbot
document.getElementById("user-input").addEventListener("keypress", (e) => {
  if (e.key === "Enter") {
    e.preventDefault() // Ngăn xuống dòng nếu dùng textarea
    sendMessage() // Gọi hàm gửi tin
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
