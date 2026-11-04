(() => {
  const island = document.querySelector(".topbar");
  if (!island) return;

  const restoreBar = document.createElement("button");
  restoreBar.className = "island-restore-bar";
  restoreBar.type = "button";
  restoreBar.setAttribute("aria-label", "Show navigation island");
  restoreBar.textContent = "Show navigation";
  document.body.appendChild(restoreBar);

  const setHidden = hidden => {
    document.body.classList.toggle("island-hidden", hidden);
    island.setAttribute("aria-hidden", String(hidden));
    if (!hidden) island.removeAttribute("aria-hidden");
  };

  document.addEventListener("keydown", event => {
    if (event.ctrlKey && event.altKey && event.key.toLowerCase() === "h") {
      event.preventDefault();
      setHidden(!document.body.classList.contains("island-hidden"));
    }
  });

  restoreBar.addEventListener("click", () => setHidden(false));
})();
