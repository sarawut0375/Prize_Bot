const input = document.getElementById("base");
chrome.storage.local.get("base").then(({ base }) => { input.value = base || "http://localhost:8000"; });
document.getElementById("save").addEventListener("click", async () => {
  const value = input.value.trim().replace(/\/+$/, "");
  if (!/^https?:\/\//.test(value)) { document.getElementById("status").textContent = "ต้องขึ้นต้นด้วย http:// หรือ https://"; return; }
  await chrome.storage.local.set({ base: value });
  document.getElementById("status").textContent = "บันทึกแล้ว";
});
