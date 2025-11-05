// function fetchQrAndStatus() {
//     fetch("http://127.0.0.1:3001/whatsapp/qr")   // 👈 Node backend ka sahi API
//       .then(response => response.json())
//       .then(data => {
//         document.getElementById('wa-qr-img').src = data.qr_code_url;
//         if (data.status === 'connected') {
//           document.getElementById('wa-qr-status').innerHTML =
//             '<i class="bi bi-check-circle-fill"></i> Connected';
//           document.getElementById('wa-qr-status').style.color = '#25d366';
//         } else {
//           document.getElementById('wa-qr-status').innerHTML =
//             '<i class="bi bi-link-45deg"></i> Not Connected';
//           document.getElementById('wa-qr-status').style.color = '#ff9800';
//         }
//       })
//       .catch(err => console.error("Error fetching QR:", err));
//   }
  