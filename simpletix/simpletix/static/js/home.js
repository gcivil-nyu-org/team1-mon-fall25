document.addEventListener("DOMContentLoaded", function () {
  // ----- Hero image rotation -----
  const heroImg = document.getElementById("hero-img");

  if (heroImg && Array.isArray(window.HERO_IMAGES) && HERO_IMAGES.length > 1) {
    let currentIndex = 0;

    function rotateHero() {
      currentIndex = (currentIndex + 1) % HERO_IMAGES.length;
      heroImg.src = HERO_IMAGES[currentIndex];
    }

    // change every 12 seconds
    setInterval(rotateHero, 12000);
  }

  // ----- "Surprise me" button -----
  const surpriseBtn = document.getElementById("surprise-me-btn");
  const cards = document.querySelectorAll(".home-pop-card");

  if (surpriseBtn && cards.length) {
    surpriseBtn.addEventListener("click", function () {
      const randomIndex = Math.floor(Math.random() * cards.length);
      const target = cards[randomIndex];

      // remove any previous highlight
      cards.forEach(c => c.classList.remove("surprise-highlight"));

      target.classList.add("surprise-highlight");
      target.scrollIntoView({ behavior: "smooth", block: "center" });

      setTimeout(() => {
        target.classList.remove("surprise-highlight");
      }, 1300);
    });
  }
});
