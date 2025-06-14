let slideIndex = 0;
const slides = document.querySelectorAll(".banner");

function showSlide(n) {
  if (n >= slides.length) {
    slideIndex = 0;
  } else if (n < 0) {
    slideIndex = slides.length - 1;
  }

  for (let i = 0; i < slides.length; i++) {
    slides[i].style.display = "none";
  }

  slides[slideIndex].style.display = "block";
}

function nextSlide() {
  slideIndex++;
  showSlide(slideIndex);
}

function prevSlide() {
  slideIndex--;
  showSlide(slideIndex);
}

// Otomatis geser slide setiap beberapa detik
setInterval(() => {
  nextSlide();
}, 5000); // Ganti 5000 dengan waktu dalam milidetik sesuai kebutuhan Anda
