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
                <p style="font-size:1.3rem;">No results found for "<strong>${query}</strong>"</p>
              </div>`;
            return;
          }

          const grid = document.createElement('div');
          grid.style.cssText = `display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 30px; margin: 30px auto; max-width: 1200px;`;

          data.forEach((person, index) => {
            // Your backend sends 'all_photos' as an array from 'images_json'
            const photos = person.all_photos || [];
            const photoArrayJson = JSON.stringify(photos).replace(/'/g, "\\'");
            const escapedName = person.name.replace(/'/g, "\\'");
           
            grid.innerHTML += `
              <div class="result-card" style="background:white; padding:25px; border-radius:15px; box-shadow:0 4px 10px rgba(0,0,0,0.1); text-align:center;">
                <img src="${person.photo}"
                     onerror="this.src='/public/default-photo.jpg'"
                     style="width:150px; height:150px; object-fit:cover; border-radius:50%; border:5px solid #003366; margin-bottom:15px;">
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
                    <button class="btn btn-primary" style="padding:8px 12px; font-size:0.85rem;" onclick="openGallery(${photoArrayJson}, '${escapedName}')">
                        <i class="fas fa-images"></i> View Photos
                    </button>
                    <button class="btn" style="background:#ff6b35; color:white; border:none; padding:8px 12px; font-size:0.85rem;" onclick="copyToClipboard(this, '${escapedName}', '${person.kc_id}', '${person.zone}')">
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

    // --- UPDATED GALLERY LOGIC ---
    let currentPhotos = [];
    let currentIndex = 0;
    let currentName = '';

    function openGallery(photos, name) {
      if (!photos || photos.length === 0) {
          alert("No images available for this record.");
          return;
      }
      // Max 4 photos as requested
      currentPhotos = photos.slice(0, 4);
      currentIndex = 0;
      currentName = name;
      updateGalleryUI();
      document.getElementById('galleryModal').style.display = 'flex';
    }

    function updateGalleryUI() {
      document.getElementById('galleryImg').src = currentPhotos[currentIndex];
      document.getElementById('galleryCaption').textContent = `${currentName} (${currentIndex + 1} of ${currentPhotos.length})`;
    }

    function closeGallery() {
      document.getElementById('galleryModal').style.display = 'none';
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

    // Modal click-to-close
    document.getElementById('galleryModal').onclick = e => {
      if (e.target.id === 'galleryModal') closeGallery();
    };

    // Keyboard shortcuts
    document.addEventListener('keydown', e => {
      if (document.getElementById('galleryModal').style.display === 'none') return;
      if (e.key === 'ArrowRight') nextImage();
      if (e.key === 'ArrowLeft') prevImage();
      if (e.key === 'Escape') closeGallery();
    });