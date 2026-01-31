// Mobile menu
document.querySelector('.menu-toggle')?.addEventListener('click', () => {
    document.querySelector('.nav-menu').classList.toggle('open');
});

// Ministry toggle
let currentMinistry = 'campus';

function setMinistry(ministry) {
    currentMinistry = ministry;
    document.getElementById('campus-btn').classList.toggle('btn-primary', ministry === 'campus');
    document.getElementById('church-btn').classList.toggle('btn-primary', ministry === 'church');
}

// Search Event Listeners
document.getElementById('search-btn-hero')?.addEventListener('click', performSearch);
document.getElementById('search-input-hero')?.addEventListener('keypress', e => {
    if (e.key === 'Enter') performSearch();
});

function performSearch() {
    const query = document.getElementById('search-input-hero').value.trim();
    const resultsDiv = document.getElementById('search-results');

    if (!query) {
        resultsDiv.innerHTML = `<p style="text-align:center;color:#c00;">Please enter a search term</p>`;
        return;
    }

    resultsDiv.innerHTML = `<p style="text-align:center; padding:40px; color:#003366;"><i class="fas fa-spinner fa-spin"></i> Searching...</p>`;

    fetch(`/api/search?q=${encodeURIComponent(query)}&ministry=${currentMinistry}`)
        .then(res => res.json())
        .then(data => {
            resultsDiv.innerHTML = '';

            if (data.length === 0) {
                resultsDiv.innerHTML = `
            <div style="text-align:center; padding:60px; color:#666;">
              <i class="fas fa-search" style="font-size:48px; color:#ddd; margin-bottom:20px;"></i>
              <p style="font-size:1.3rem;">No results found for "<strong>${query}</strong>"</p>
            </div>`;
                return;
            }

            const grid = document.createElement('div');
            grid.style.cssText = `display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 30px; margin: 30px auto; max-width: 1200px;`;

            data.forEach((person) => {
                // --- FIX STARTS HERE ---
                const photos = person.all_photos || [];
                
                // 1. We replace double quotes (") with &quot; so it doesn't break the HTML attribute
                const photoArrayJson = JSON.stringify(photos).replace(/"/g, '&quot;');
                
                // 2. We escape single quotes (') for the name string
                const safeName = person.name.replace(/'/g, "\\'");
                // --- FIX ENDS HERE ---

                grid.innerHTML += `
            <div class="result-card" style="background:white; padding:25px; border-radius:15px; box-shadow:0 4px 10px rgba(0,0,0,0.1); text-align:center;">
              <img src="${person.photo}"
                   onerror="this.src='/public/default-photo.jpg'"
                   style="width:150px; height:150px; object-fit:cover; border-radius:50%; border:5px solid #003366; margin-bottom:15px; cursor:pointer;"
                   onclick="openGallery(${photoArrayJson}, '${safeName}')">
                   
              <h3 style="color:#003366; margin:10px 0;">${person.name}</h3>
             
              <div style="text-align:left; font-size:0.9rem; margin-bottom:20px; line-height:1.4;">
                  <p><strong>Designation:</strong> ${person.designation || '—'}</p>
                  <p><strong>KC ID:</strong> ${person.kc_id || '—'}</p>
                  <p><strong>Zone:</strong> ${person.zone || '—'}</p>
                  <p><strong>Region:</strong> ${person.region || '—'}</p>
                  <p><strong>Group:</strong> ${person.group || '—'}</p>
                  <p><strong>Chapter:</strong> ${person.chapter || '—'}</p>
              </div>

              <div style="display:flex; gap:10px; justify-content:center;">
                  <button class="btn btn-primary" style="background:#ff6b35; color:white; border:none; padding:8px 12px; font-size:0.85rem; cursor:pointer;" 
                          onclick="openGallery(${photoArrayJson}, '${safeName}')">
                      <i class="fas fa-images"></i> View Photos (${photos.length})
                  </button>
                  <button class="btn" style="background:#003366; color:white; border:none; padding:8px 12px; font-size:0.85rem; cursor:pointer;" 
                          onclick="copyToClipboard(this, '${safeName}', '${person.kc_id || ''}', '${person.zone || ''}')">
                      <i class="fas fa-copy"></i> Copy Info
                  </button>
              </div>
            </div>
          `;
            });

            resultsDiv.appendChild(grid);
            
            // Ensure Modal Exists (Self-Healing)
            ensureModalExists();
        })
        .catch(err => {
            console.error(err);
            resultsDiv.innerHTML = `<p style="text-align:center;color:#c00;">Error loading results.</p>`;
        });
}

// --- HELPER: Copy Info ---
function copyToClipboard(btn, name, kcid, zone) {
    const text = `Record Name: ${name}\nKC ID: ${kcid}\nZone: ${zone}`;
    navigator.clipboard.writeText(text).then(() => {
        const oldHtml = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-check"></i> Copied!';
        setTimeout(() => { btn.innerHTML = oldHtml; }, 2000);
    });
}

// --- GALLERY LOGIC ---
let currentPhotos = [];
let currentIndex = 0;
let currentName = '';

function ensureModalExists() {
    if (!document.getElementById('galleryModal')) {
        const modalHtml = `
        <div id="galleryModal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9); z-index:1000; justify-content:center; align-items:center; flex-direction:column;">
            <button onclick="closeGallery()" style="position:absolute; top:20px; right:30px; background:none; border:none; color:white; font-size:40px; cursor:pointer;">&times;</button>
            
            <img id="galleryImg" src="" style="max-width:90%; max-height:80vh; border:2px solid white; border-radius:5px;">
            
            <p id="galleryCaption" style="color:white; margin-top:15px; font-size:1.2rem;"></p>
            
            <div style="display:flex; gap:20px; margin-top:15px;">
                <button onclick="prevImage()" style="background:#ff6b35; border:none; color:white; padding:10px 20px; font-size:1.2rem; cursor:pointer; border-radius:5px;"><i class="fas fa-arrow-left"></i> Prev</button>
                <button onclick="nextImage()" style="background:#ff6b35; border:none; color:white; padding:10px 20px; font-size:1.2rem; cursor:pointer; border-radius:5px;">Next <i class="fas fa-arrow-right"></i></button>
            </div>
        </div>`;
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        // Add click-outside-to-close
        document.getElementById('galleryModal').addEventListener('click', function(e) {
            if (e.target === this) closeGallery();
        });
    }
}

function openGallery(photos, name) {
    if (!photos || photos.length === 0) {
        alert("No images available for this record.");
        return;
    }
    
    // Ensure modal exists just in case
    ensureModalExists();

    currentPhotos = photos;
    currentIndex = 0;
    currentName = name;
    
    updateGalleryUI();
    document.getElementById('galleryModal').style.display = 'flex';
}

function updateGalleryUI() {
    const imgElement = document.getElementById('galleryImg');
    const captionElement = document.getElementById('galleryCaption');
    
    if(imgElement) imgElement.src = currentPhotos[currentIndex];
    if(captionElement) captionElement.textContent = `${currentName} - Photo ${currentIndex + 1} of ${currentPhotos.length}`;
}

function closeGallery() {
    const modal = document.getElementById('galleryModal');
    if(modal) modal.style.display = 'none';
}

function nextImage() {
    if (currentPhotos.length <= 1) return;
    currentIndex = (currentIndex + 1) % currentPhotos.length;
    updateGalleryUI();
}

function prevImage() {
    if (currentPhotos.length <= 1) return;
    currentIndex = (currentIndex - 1 + currentPhotos.length) % currentPhotos.length;
    updateGalleryUI();
}

// Keyboard navigation
document.addEventListener('keydown', e => {
    const modal = document.getElementById('galleryModal');
    if (!modal || modal.style.display === 'none') return;
    
    if (e.key === 'ArrowRight') nextImage();
    if (e.key === 'ArrowLeft') prevImage();
    if (e.key === 'Escape') closeGallery();
});