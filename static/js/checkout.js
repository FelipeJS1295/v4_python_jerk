// checkout.js

let currentStep = 1;
let cartItems = [];

const comunasPorRegion = {
  "Metropolitana": ["Santiago", "Las Condes", "Providencia", "Ñuñoa", "La Reina"],
  "Valparaíso": ["Valparaíso", "Viña del Mar", "Concón"],
  "O'Higgins": ["Rancagua", "Machalí", "San Fernando"],
  "Maule": ["Talca", "Curicó", "Linares"],
  "Biobío": ["Concepción", "Los Ángeles", "Coronel"],
  "Araucanía": ["Temuco", "Padre las Casas", "Villarrica"]
};

document.addEventListener('DOMContentLoaded', function () {
  loadCartItems();
  renderCheckoutSteps();
  initializeEventListeners();
  updateProgress();
});

function loadCartItems() {
  const cart = JSON.parse(localStorage.getItem('cart')) || [];
  cartItems = cart;
  if (cartItems.length === 0) {
    window.location.href = '/productos';
    return;
  }
  displayCartItems();
  calculateTotals();
}

function displayCartItems() {
  const container = document.getElementById('cart-items');
  container.innerHTML = '';
  cartItems.forEach(item => {
    const div = document.createElement('div');
    div.className = 'flex items-center space-x-3 p-3 bg-dark-900/50 rounded-lg';
    div.innerHTML = `
      <div class="w-16 h-16 bg-gray-700 rounded-lg flex items-center justify-center">
        ${item.imagen ? `<img src="${item.imagen}" class="w-full h-full object-cover rounded-lg">` : `<i class="fas fa-image text-gray-500"></i>`}
      </div>
      <div class="flex-1 min-w-0">
        <h4 class="text-sm font-medium text-white truncate">${item.nombre}</h4>
        <p class="text-sm text-white/60">Cantidad: ${item.cantidad}</p>
        <p class="text-sm font-medium text-brand-coral-400">$${formatNumber(item.precio * item.cantidad)}</p>
      </div>
    `;
    container.appendChild(div);
  });
}

function calculateTotals() {
  const subtotal = cartItems.reduce((total, item) => total + (item.precio * item.cantidad), 0);
  const total = subtotal;
  document.getElementById('subtotal').textContent = formatNumber(subtotal);
  document.getElementById('total').textContent = formatNumber(total);

  const fecha = new Date();
  fecha.setDate(fecha.getDate() + 3);
  document.getElementById('delivery-date').textContent = fecha.toLocaleDateString('es-CL', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
  });
}

function formatNumber(n) {
  return new Intl.NumberFormat('es-CL').format(n);
}

function renderCheckoutSteps() {
  const container = document.getElementById('checkout-steps');
  fetch('/static/html/checkout_steps.html')
    .then(res => res.text())
    .then(html => {
      container.innerHTML = html;
      initializeEventListeners();
    })
    .catch(err => {
      console.error('Error al cargar los pasos del checkout:', err);
    });
}

function initializeEventListeners() {
  const regionSelect = document.getElementById('region');
  const comunaSelect = document.getElementById('comuna');

  if (regionSelect) {
    regionSelect.addEventListener('change', () => {
      const region = regionSelect.value;
      comunaSelect.innerHTML = '<option value="">Selecciona una comuna</option>';
      if (comunasPorRegion[region]) {
        comunasPorRegion[region].forEach(comuna => {
          const option = document.createElement('option');
          option.value = comuna;
          option.textContent = comuna;
          comunaSelect.appendChild(option);
        });
      }
    });
  }

  const nextBtns = document.querySelectorAll('[id^="btn-step-"]');
  nextBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const step = parseInt(btn.id.replace('btn-step-', ''));
      goToStep(step + 1);
    });
  });

  const backBtns = document.querySelectorAll('[id^="btn-back-"]');
  backBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const step = parseInt(btn.id.replace('btn-back-', ''));
      goToStep(step);
    });
  });

  document.getElementById('btn-finalizar')?.addEventListener('click', finalizarCompra);
}

function goToStep(step) {
  document.querySelectorAll('.step-content').forEach(el => el.classList.add('hidden'));
  document.getElementById(`step-${step}`).classList.remove('hidden');
  currentStep = step;
  updateProgress();
}

function updateProgress() {
  const progressBar = document.getElementById('progress-bar');
  const positions = ['10%', '35%', '60%', '85%'];
  progressBar.style.width = `${(currentStep / 4) * 100}%`;
  const truck = document.getElementById('truck-animation');
  truck.style.left = positions[currentStep - 1];

  for (let i = 1; i <= 4; i++) {
    const label = document.getElementById(`step-${i}-label`);
    const circle = label.querySelector('div');
    if (i <= currentStep) {
      label.classList.add('text-brand-coral-400');
      label.classList.remove('text-white/40');
      circle.classList.add('bg-brand-coral-500', 'text-white');
      circle.classList.remove('bg-white/10', 'text-white/50');
    } else {
      label.classList.remove('text-brand-coral-400');
      label.classList.add('text-white/40');
      circle.classList.remove('bg-brand-coral-500', 'text-white');
      circle.classList.add('bg-white/10', 'text-white/50');
    }
  }
}

async function finalizarCompra() {
  // Tu lógica de envío al backend
  console.log("Finalizar compra");
  document.getElementById('loading-overlay').classList.remove('hidden');
  setTimeout(() => {
    localStorage.removeItem('cart');
    window.location.href = '/compra-exitosa';
  }, 2000);
}