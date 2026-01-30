// public/js/search.js

document.addEventListener('DOMContentLoaded', () => {
  const searchInput = document.getElementById('searchInput');
  const ministrySelect = document.getElementById('ministrySelect');
  const searchBtn = document.getElementById('searchBtn');
  const resultsDiv = document.getElementById('results');

  // Search triggers
  searchBtn.addEventListener('click', performSearch);
  searchInput.addEventListener('keypress', e => {
    if (e.key === 'Enter') performSearch();
  });

  async function performSearch() {
    const query = searchInput.value.trim();
    const ministry = ministrySelect.value;

    if (!query) {
      resultsDiv.innerHTML = '<p class="no-results">Please enter a name or KC ID</p>';
      return;
    }

    resultsDiv.innerHTML = '<p class="loading">Searching...</p>';

    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(query)}&ministry=${ministry}`);
      const data = await res.json();

      if (data.length === 0) {
        resultsDiv.innerHTML = '<p class="no-results">No records found</p>';
        return;
      }

      displayResults(data);
    } catch (err) {
      resultsDiv.innerHTML = '<p class="error">Error searching records</p>';
      console.error(err);
    }
  }

  function displayResults(people) {
    resultsDiv.innerHTML = '';

    people.forEach(person => {
      const personCard = document.createElement('div');
      personCard.className = 'person-card';

      personCard.innerHTML = `
        <h2 class="person-name">${person.name}</h2>
        <div class="person-info">
          <p><strong>Designation:</strong> ${person.designation || '—'}</p>
          <p><strong>KC ID:</strong> ${person.kc_id || '—'}</p>
          <p><strong>Region:</strong> ${person.region || '—'}</p>
          <p><strong>Group:</strong> ${person.group || '—'}</p>
          ${person.zone ? `<p><strong>Zone:</strong> ${person.zone}</p>` : ''}
          ${person.chapter ? `<p><strong>Chapter:</strong> ${person.chapter}</p>` : ''}
        </div>
      `;

      // Multi-photo display with download buttons
      const photosDiv = document.createElement('div');
      photosDiv.className = 'photos-container';

      if (person.all_photos && person.all_photos.length > 0) {
        person.all_photos.forEach((photoUrl, index) => {
          const wrapper = document.createElement('div');
          wrapper.className = 'photo-wrapper';

          const img = document.createElement('img');
          img.src = photoUrl;
          img.alt = `Photo ${index + 1} of ${person.name}`;
          img.onclick = () => openGallery(person.all_photos, index, person.name);

          const downloadLink = document.createElement('a');
          downloadLink.href = photoUrl;
          downloadLink.download = `${person.name.replace(/\s+/g, '_')}_photo_${index + 1}${photoUrl.match(/\.[^.]+$/)?.[0] || '.jpg'}`;
          downloadLink.title = 'Download this photo';
          downloadLink.className = 'download-btn';
          downloadLink.innerHTML = '<i class="fas fa-download"></i>';

          wrapper.appendChild(img);
          wrapper.appendChild(downloadLink);
          photosDiv.appendChild(wrapper);
        });
      } else {
        const noPhoto = document.createElement('p');
        noPhoto.className = 'no-photos';
        noPhoto.textContent = 'No photos available';
        photosDiv.appendChild(noPhoto);
      }

      personCard.appendChild(photosDiv);
      resultsDiv.appendChild(personCard);
    });
  }

  // Gallery functions (original - untouched)
  let currentPhotos = [];
  let currentIndex = 0;
  let currentName = '';

  function openGallery(photos, index, name) {
    currentPhotos = photos;
    currentIndex = index;
    currentName = name;

    document.getElementById('galleryImg').src = photos[index];
    document.getElementById('galleryCaption').textContent = `${name} (${index + 1} of ${photos.length})`;
    document.getElementById('galleryModal').style.display = 'flex';
  }

  function closeGallery() {
    document.getElementById('galleryModal').style.display = 'none';
  }

  function nextImage() {
    currentIndex = (currentIndex + 1) % currentPhotos.length;
    updateGalleryImage();
  }

  function prevImage() {
    currentIndex = (currentIndex - 1 + currentPhotos.length) % currentPhotos.length;
    updateGalleryImage();
  }

  function updateGalleryImage() {
    document.getElementById('galleryImg').src = currentPhotos[currentIndex];
    document.getElementById('galleryCaption').textContent = `${currentName} (${currentIndex + 1} of ${currentPhotos.length})`;
  }

  document.getElementById('galleryModal').onclick = e => {
    if (e.target.id === 'galleryModal') closeGallery();
  };

  document.getElementById('prevBtn').onclick = prevImage;
  document.getElementById('nextBtn').onclick = nextImage;

  document.addEventListener('keydown', e => {
    if (document.getElementById('galleryModal').style.display === 'none') return;
    if (e.key === 'ArrowRight') nextImage();
    if (e.key === 'ArrowLeft') prevImage();
    if (e.key === 'Escape') closeGallery();
  });
});