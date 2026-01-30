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

// Search
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
            <p style="font-size:1.3rem;">No results found for "<strong>${query}</strong>" in ${currentMinistry === 'campus' ? 'BLW Campus' : 'Christ Embassy Church'} Ministry</p>
          </div>`;
        return;
      }

      const grid = document.createElement('div');
      grid.style.cssText = `
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 30px;
        margin: 30px 0;
        max-width: 1200px;
        margin: 0 auto;
      `;

      data.forEach(person => {
        // Prepare variables for the copy feature
        const designation = person.designation || '—';
        const kcid = person.kc_id || '—';
        const zone = person.zone || person.blw_zone || '—';
        const region = person.region || '—';
        const group = person.group || person.group_name || '—';
        const chapter = person.chapter || person.church || '—';
       
        // Escape name for JSON string usage in the onclick attributes
        const escapedName = person.name.replace(/'/g, "\\'");
        const photoArrayJson = JSON.stringify(person.all_photos).replace(/'/g, "\\'");

        grid.innerHTML += `
          <div class="result-card" style="background:white; padding:25px; border-radius:15px; box-shadow:0 4px 10px rgba(0,0,0,0.1); text-align:center; transition:0.3s;">
            <img src="${person.photo}"
                 onerror="this.src='/public/default-photo.jpg'"
                 style="width:150px; height:150px; object-fit:cover; border-radius:50%; border:5px solid #003366; margin-bottom:15px;">
            <h3 style="color:#003366; margin:10px 0;">${person.name}</h3>
            <div style="text-align:left; font-size:0.9rem; margin-bottom:20px;">
                <p style="margin:5px 0; color:#444;"><strong>Designation:</strong> ${designation}</p>
                <p style="margin:5px 0; color:#444;"><strong>KC ID:</strong> ${kcid}</p>
                <p style="margin:5px 0; color:#444;"><strong>Zone:</strong> ${zone}</p>
                <p style="margin:5px 0; color:#444;"><strong>Region:</strong> ${region}</p>
                <p style="margin:5px 0; color:#444;"><strong>Group:</strong> ${group}</p>
                <p style="margin:5px 0; color:#444;"><strong>Chapter:</strong> ${chapter}</p>
            </div>
           
            <div style="display:flex; gap:10px; justify-content:center;">
                <button class="btn btn-primary" style="background:#003366; padding:8px 15px; font-size:0.85rem;" onclick="openGallery(${photoArrayJson}, '${escapedName}')">
                    <i class="fas fa-images"></i> View Photos
                </button>
                <button class="btn" style="background:#ff6b35; color:white; border:none; padding:8px 15px; font-size:0.85rem;" onclick="copyToClipboard(this, '${escapedName}', '${designation}', '${kcid}', '${zone}', '${region}', '${group}', '${chapter}')">
                    <i class="fas fa-copy"></i> Copy Info
                </button>
            </div>
          </div>
        `;
      });

      resultsDiv.appendChild(grid);
    })
    .catch(err => {
      console.error(err);
      resultsDiv.innerHTML = `<p style="text-align:center;color:#c00;">Error loading results. Please try again.</p>`;
    });
}

// Helper function to copy info
function copyToClipboard(btn, name, desig, kc, zone, reg, grp, chap) {
    const text = `ROR DATAHUB RECORD:
Name: ${name}
Designation: ${desig}
KC ID: ${kc}
Zone: ${zone}
Region: ${reg}
Group: ${grp}
Chapter: ${chap}`;

    navigator.clipboard.writeText(text).then(() => {
        const originalText = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-check"></i> Copied!';
        btn.style.background = '#27ae60';
        setTimeout(() => {
            btn.innerHTML = originalText;
            btn.style.background = '#ff6b35';
        }, 2000);
    });
}

// Gallery Logic
let currentPhotos = [];
let currentIndex = 0;
let currentName = '';

function openGallery(photos, name) {
  if (!photos || photos.length === 0) {
      alert("No photos available for this record.");
      return;
  }
  // Max 4 photos as requested
  currentPhotos = photos.slice(0, 4);
  currentIndex = 0;
  currentName = name;
  document.getElementById('galleryImg').src = currentPhotos[0];
  document.getElementById('galleryCaption').textContent = `${name} (1 of ${currentPhotos.length})`;
  document.getElementById('galleryModal').style.display = 'flex';
}

function closeGallery() {
  document.getElementById('galleryModal').style.display = 'none';
}

function nextImage() {
  currentIndex = (currentIndex + 1) % currentPhotos.length;
  document.getElementById('galleryImg').src = currentPhotos[currentIndex];
  document.getElementById('galleryCaption').textContent = `${currentName} (${currentIndex + 1} of ${currentPhotos.length})`;
}

function prevImage() {
  currentIndex = (currentIndex - 1 + currentPhotos.length) % currentPhotos.length;
  document.getElementById('galleryImg').src = currentPhotos[currentIndex];
  document.getElementById('galleryCaption').textContent = `${currentName} (${currentIndex + 1} of ${currentPhotos.length})`;
}

document.getElementById('galleryModal').onclick = e => {
  if (e.target.id === 'galleryModal') closeGallery();
};

document.addEventListener('keydown', e => {
  if (document.getElementById('galleryModal').style.display === 'none') return;
  if (e.key === 'ArrowRight') nextImage();
  if (e.key === 'ArrowLeft') prevImage();
  if (e.key === 'Escape') closeGallery();
});        