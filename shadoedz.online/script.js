const progress = document.getElementById("progress");
const menuBtn = document.getElementById("menuBtn");
const navLinks = document.getElementById("navLinks");

window.addEventListener("scroll", () => {
  const max = document.documentElement.scrollHeight - window.innerHeight;
  progress.style.width = `${(window.scrollY / max) * 100}%`;
});

menuBtn.addEventListener("click", () => navLinks.classList.toggle("open"));
document.querySelectorAll("#navLinks a").forEach(a => {
  a.addEventListener("click", () => navLinks.classList.remove("open"));
});

document.getElementById("year").textContent = new Date().getFullYear();
