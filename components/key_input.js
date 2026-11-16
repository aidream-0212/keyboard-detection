// 키 입력 상자: 키를 누른 시각과 뗀 시각을 브라우저에서 재서 파이썬으로 보낸다.
// Streamlit 의 st.components.v2 방식이다. (빌드 단계 없음)

// 화면에 올라간 상자마다 따로 기억할 값 (events: 이번 시도의 키 기록)
const stores = new WeakMap()

// 물리 키 이름(event.code)을 화면에 보여줄 글자로 바꾼다. 한/영 상태와 무관하다.
function charFromCode(code) {
  if (code.startsWith("Key")) return code.slice(3).toLowerCase()
  if (code.startsWith("Digit")) return code.slice(5)
  if (code === "Space") return " "
  return ""
}

export default function (component) {
  const { data, parentElement, setTriggerValue } = component
  const box = parentElement.querySelector(".box")
  const typed = parentElement.querySelector(".typed")
  if (!box || !typed) return

  // 이 함수는 파이썬이 다시 실행될 때마다 또 불린다. 처음 한 번만 값을 만든다.
  let store = stores.get(parentElement)
  if (!store) {
    store = { events: [], text: "", capsLock: false, lastId: 0 }
    stores.set(parentElement, store)
    box.focus()
  }
  // 시도 번호는 파이썬이 마지막으로 처리한 번호보다 항상 커야 한다
  store.lastId = Math.max(store.lastId, (data && data.last_id) || 0)

  function showText() {
    typed.textContent = store.text
    box.classList.toggle("has-text", store.text.length > 0)
  }

  function reset() {
    store.events = []
    store.text = ""
    store.capsLock = false
    showText()
  }

  function isShortcut(e) {
    // Ctrl+R 같은 단축키와 Tab 이동은 건드리지 않는다
    return e.ctrlKey || e.metaKey || e.altKey || e.code === "Tab"
  }

  box.onkeydown = (e) => {
    if (isShortcut(e)) return
    e.preventDefault()
    if (e.repeat) return // 꾹 눌러서 생기는 반복 입력은 무시
    if (e.getModifierState("CapsLock")) store.capsLock = true

    store.events.push({ code: e.code, type: "down", t: performance.now() })

    if (e.code === "Backspace") {
      store.text = store.text.slice(0, -1)
    } else {
      store.text += charFromCode(e.code)
    }
    showText()
  }

  box.onkeyup = (e) => {
    if (isShortcut(e)) return
    store.events.push({ code: e.code, type: "up", t: performance.now() })
    if (e.code !== "Enter") return

    // 이 상자에서 Enter 를 누른 적이 없으면(다른 곳에서 누르고 여기서 뗀 경우) 보내지 않는다
    const enterWasPressedHere = store.events.some(
      (ev) => ev.code === "Enter" && ev.type === "down"
    )
    if (enterWasPressedHere) {
      store.lastId += 1
      setTriggerValue("attempt", {
        id: store.lastId,
        events: store.events,
        caps_lock: store.capsLock,
      })
    }
    reset()
  }

  // 입력 도중 다른 곳을 클릭하면 시간이 끊기므로 처음부터 다시 받는다
  box.onblur = reset

  showText()
}
