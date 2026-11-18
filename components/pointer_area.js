// 포인터 연습 영역: 마우스·터치패드의 움직임과 클릭을 기록해 파이썬으로 보낸다.
// 동작을 나누고 특징을 계산하는 일은 파이썬(core/pointer.py)이 한다.
// 여기서는 기록을 모았다가, 클릭이 끝나거나 0.5초 멈추거나 영역을 벗어날 때 한 묶음으로 보낸다.

const SAMPLE_MS = 30   // 움직임은 30ms 에 한 번만 기록한다 (앱을 가볍게 하기 위해)
const PAUSE_MS = 500   // 이만큼 멈추면 묶음을 보낸다
const ITEMS = [
  "1중대 일일 보고", "2중대 일일 보고", "3중대 일일 보고", "보급 요청 A-12", "보급 요청 B-07",
  "통신 점검 결과", "장비 정비 일정", "훈련 계획(가상)", "기상 정보", "도로 상황",
  "인원 현황 표", "차량 배치 표", "야간 근무 명단", "점검 체크리스트", "회의 기록(가상)",
  "지도 레이어 1", "지도 레이어 2", "연락처(가상)", "공지 사항", "변경 이력",
]

// 화면에 올라간 영역마다 따로 기억할 값
const stores = new WeakMap()

export default function (component) {
  const { data, parentElement, setTriggerValue } = component
  const area = parentElement.querySelector(".area")
  const list = parentElement.querySelector(".list")
  const targetName = parentElement.querySelector(".target-name")
  if (!area || !list || !targetName) return

  // 이 함수는 파이썬이 다시 실행될 때마다 또 불린다. 처음 한 번만 준비한다.
  let store = stores.get(parentElement)
  if (!store) {
    store = { events: [], lastMoveT: -Infinity, pressed: false, timer: null, lastId: 0 }
    stores.set(parentElement, store)
    for (const text of ITEMS) {
      const item = document.createElement("li")
      item.textContent = text
      item.dataset.name = text
      list.appendChild(item)
    }
    pickTarget()
  }
  store.lastId = Math.max(store.lastId, (data && data.last_id) || 0)

  // 다음에 누를 메뉴를 하나 골라 테두리로 표시한다 (움직일 이유를 주기 위해)
  function pickTarget() {
    const choices = parentElement.querySelectorAll(".menu, .list li")
    choices.forEach((el) => el.classList.remove("target"))
    const next = choices[Math.floor(Math.random() * choices.length)]
    next.classList.add("target")
    targetName.textContent = next.dataset.name
  }

  // 시각은 이벤트가 실제로 생긴 순간(e.timeStamp)을 쓴다. 처리 시점(performance.now())을 쓰면
  // 화면을 다시 그리느라 브라우저가 바쁠 때 기록이 늦게 찍혀 가짜 '멈춤'이 생길 수 있다.
  function record(type, e) {
    store.events.push({ type, t: e.timeStamp, x: e.clientX, y: e.clientY })
  }

  function send() {
    clearTimeout(store.timer)
    if (store.events.length === 0) return
    store.lastId += 1
    setTriggerValue("batch", { id: store.lastId, events: store.events })
    store.events = []
  }

  function sendAfterPause() {
    clearTimeout(store.timer)
    store.timer = setTimeout(send, PAUSE_MS)
  }

  area.onpointermove = (e) => {
    const t = e.timeStamp
    if (t - store.lastMoveT < SAMPLE_MS) return
    store.lastMoveT = t
    record("move", e)
    if (!store.pressed) sendAfterPause()
  }

  area.onpointerdown = (e) => {
    clearTimeout(store.timer)
    store.pressed = true
    record("down", e)
  }

  area.onpointerup = (e) => {
    record("up", e)
    store.pressed = false
    if (e.target.closest(".target")) pickTarget()
    send()
  }

  area.onpointerleave = () => {
    store.pressed = false
    send()
  }
}
