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
            const photoCount = person.all_photos.length;
            grid.innerHTML += `
              <div class="result-card" style="cursor:pointer;" onclick="openGallery(${JSON.stringify(person.all_photos)}, '${person.name.replace(/'/g, "\\'")}')">
                <img src="${person.photo}" 
                     onerror="this.src='/public/default-photo.jpg'"
                     style="width:150px; height:150px; object-fit:cover; border-radius:50%; border:5px solid #003366; margin-bottom:15px;">
                <h3 style="color:#003366; margin:10px 0;">${person.name}</h3>
                <p style="margin:8px 0; color:#444;"><strong>Designation:</strong> ${person.designation || '—'}</p>
                <p style="margin:8px 0; color:#444;"><strong>KC ID:</strong> ${person.kc_id || '—'}</p>
                <p style="margin:8px 0; color:#444;"><strong>Zone:</strong> ${person.zone || person.blw_zone || '—'}</p>
                <p style="margin:8px 0; color:#444;"><strong>Region:</strong> ${person.region || '—'}</p>
                <p style="margin:8px 0; color:#444;"><strong>Group:</strong> ${person.group || person.group_name || '—'}</p>
                <p style="margin:8px 0; color:#444;"><strong>Chapter/Church:</strong> ${person.chapter || person.church || '—'}</p>
                ${photoCount > 1 ? `<p style="margin-top:15px; color:#003366; font-weight:bold;">📸 Click to view all ${photoCount} photos</p>` : ''}
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

    // Gallery
    let currentPhotos = [];
    let currentIndex = 0;
    let currentName = '';

    function openGallery(photos, name) {
      if (!photos || photos.length === 0) return;
      currentPhotos = photos;
      currentIndex = 0;
      currentName = name;
      document.getElementById('galleryImg').src = photos[0];
      document.getElementById('galleryCaption').textContent = `${name} (1 of ${photos.length})`;
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
