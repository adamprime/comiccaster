document.addEventListener('DOMContentLoaded', function() {
  // Create toast element
  const toastEl = document.createElement('div');
  toastEl.className = 'toast-notification';
  toastEl.setAttribute('role', 'alert');
  document.body.appendChild(toastEl);

  // Function to show toast notification
  function showToast(message) {
    toastEl.textContent = message;
    toastEl.style.display = 'block';
    setTimeout(() => {
      toastEl.style.display = 'none';
    }, 2000);
  }

  // Function to copy text to clipboard
  async function copyToClipboard(text) {
    try {
      await navigator.clipboard.writeText(text);
      showToast('Feed URL copied to clipboard!');
    } catch (err) {
      showToast('Failed to copy URL');
      console.error('Failed to copy:', err);
    }
  }

  // Fetch available comics from the server
  async function fetchAvailableComics() {
    try {
      const response = await fetch('/.netlify/functions/list-comics');
      if (!response.ok) {
        throw new Error('Failed to fetch available comics');
      }
      return await response.json();
    } catch (error) {
      console.error('Error fetching available comics:', error);
      return [];
    }
  }

  // Initialize the comic list
  async function initializeComicList() {
    const comics = await fetchAvailableComics();
    const comicList = document.getElementById('comic-list');
    
    comics.forEach(comic => {
      const div = document.createElement('div');
      div.className = 'bg-gray-700 p-4 rounded flex justify-between items-center';
      div.innerHTML = `
        <div>
          <h3 class="font-semibold">${comic.name}</h3>
        </div>
        <div class="flex space-x-4">
          <a href="/feeds/${comic.slug}.xml" 
             class="text-blue-400 hover:text-blue-300 flex items-center">
            <svg class="w-5 h-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                    d="M6 5c7.18 0 13 5.82 13 13M6 11a7 7 0 017 7m-6 0a1 1 0 110-2 1 1 0 010 2z"/>
            </svg>
            RSS Feed
          </a>
          <a href="https://www.gocomics.com/${comic.slug}" 
             target="_blank"
             class="text-gray-400 hover:text-gray-300">
            View Comic
          </a>
        </div>
      `;
      comicList.appendChild(div);
    });
  }

  // Filter comics based on search input
  function setupSearch() {
    const searchInput = document.getElementById('searchInput');
    const comicList = document.getElementById('comic-list');
    
    searchInput.addEventListener('input', () => {
      const searchTerm = searchInput.value.toLowerCase();
      const comics = comicList.children;
      
      Array.from(comics).forEach(comic => {
        const title = comic.querySelector('h3').textContent.toLowerCase();
        comic.style.display = title.includes(searchTerm) ? 'flex' : 'none';
      });
    });
  }

  // Handle custom feed generation
  async function setupCustomFeedGeneration() {
    const customSearchInput = document.getElementById('customSearchInput');
    const selectedComics = document.getElementById('selected-comics');
    const generateButton = document.getElementById('generate-opml');
    const resetButton = document.getElementById('reset-selection');
    
    const comics = await fetchAvailableComics();
    let selectedSlugs = new Set();
    
    function updateSelectedComics() {
      selectedComics.innerHTML = '';
      selectedSlugs.forEach(slug => {
        const comic = comics.find(c => c.slug === slug);
        if (comic) {
          const div = document.createElement('div');
          div.className = 'bg-gray-700 p-2 rounded flex justify-between items-center';
          div.innerHTML = `
            <span>${comic.name}</span>
            <button class="text-red-400 hover:text-red-300" onclick="removeComic('${comic.slug}')">
              Remove
            </button>
          `;
          selectedComics.appendChild(div);
        }
      });
    }
    
    window.removeComic = (slug) => {
      selectedSlugs.delete(slug);
      updateSelectedComics();
    };
    
    generateButton.addEventListener('click', async () => {
      if (selectedSlugs.size === 0) {
        alert('Please select at least one comic');
        return;
      }
      
      try {
        const response = await fetch('/.netlify/functions/generate-opml', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ comics: Array.from(selectedSlugs) })
        });
        
        if (!response.ok) {
          throw new Error('Failed to generate OPML file');
        }
        
        const opmlContent = await response.text();
        const blob = new Blob([opmlContent], { type: 'application/xml' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'comiccaster-feeds.opml';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        
        // Show success modal
        const successModal = new bootstrap.Modal(document.getElementById('successModal'));
        successModal.show();
      } catch (error) {
        console.error('Error:', error);
        alert('Failed to generate OPML file. Please try again.');
      }
    });
    
    resetButton.addEventListener('click', () => {
      selectedSlugs.clear();
      updateSelectedComics();
    });
  }

  // Initialize everything when the page loads
  document.addEventListener('DOMContentLoaded', () => {
    initializeComicList();
    setupSearch();
    setupCustomFeedGeneration();
  });

  // Load comics list
  fetch('/comics_list.json')
    .then(response => response.json())
    .then(comics => {
      // Populate individual feeds table
      const tableBody = document.getElementById('comicTableBody');
      const tableContainer = document.createElement('div');
      tableContainer.className = 'table-container';
      
      comics.forEach(comic => {
        const row = document.createElement('tr');
        const feedUrl = `${window.location.origin}/rss/${comic.slug}`;
        const sourceUrl = `https://www.gocomics.com/${comic.slug}`;
        row.innerHTML = `
          <td>${comic.name}</td>
          <td>
            <div class="feed-url-container">
              <svg class="copy-icon" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                <path d="M4 2a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V2z"/>
                <path d="M2 4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V4z"/>
              </svg>
              <code class="feed-url" data-url="${feedUrl}">${feedUrl}</code>
            </div>
          </td>
          <td>
            <a href="${sourceUrl}" target="_blank" rel="noopener noreferrer" class="source-link">
              🔗 Source
            </a>
          </td>
        `;
        tableBody.appendChild(row);

        // Add click handler for copy icon
        const copyIcon = row.querySelector('.copy-icon');
        copyIcon.addEventListener('click', () => {
          copyToClipboard(feedUrl);
        });

        // Add click handler for feed URL
        const feedUrlEl = row.querySelector('.feed-url');
        feedUrlEl.addEventListener('click', () => {
          copyToClipboard(feedUrl);
        });
      });

      // Populate comic selection checkboxes
      const checkboxContainer = document.getElementById('comicCheckboxes');
      comics.forEach(comic => {
        const div = document.createElement('div');
        div.className = 'form-check comic-item';
        div.setAttribute('data-comic-name', comic.name.toLowerCase());
        div.innerHTML = `
          <input class="form-check-input" type="checkbox" name="comics" value="${comic.slug}" id="comic-${comic.slug}">
          <label class="form-check-label" for="comic-${comic.slug}">
            ${comic.name}
          </label>
        `;
        checkboxContainer.appendChild(div);
      });

      // Add search functionality
      setupSearch();
    })
    .catch(error => {
      console.error('Error loading comics:', error);
      document.getElementById('comicTableBody').innerHTML = '<tr><td colspan="3">Error loading comics. Please try again later.</td></tr>';
    });

  // Handle form submission
  document.getElementById('comicSelectForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    // Get selected comics
    const selectedComics = Array.from(document.querySelectorAll('input[name="comics"]:checked'))
      .map(checkbox => checkbox.value);
    
    if (selectedComics.length === 0) {
      alert('Please select at least one comic');
      return;
    }
    
    try {
      // Generate OPML file
      const response = await fetch('/.netlify/functions/generate-opml', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ comics: selectedComics })
      });
      
      if (!response.ok) {
        throw new Error('Failed to generate OPML file');
      }

      // Get the OPML content
      const opmlContent = await response.text();
      
      // Create a blob and download link
      const blob = new Blob([opmlContent], { type: 'application/xml' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'comiccaster-feeds.opml';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      // Show success message
      showSuccessMessage();
    } catch (error) {
      console.error('Error:', error);
      alert(`Error: ${error.message}`);
    }
  });

  function showSuccessMessage() {
    // Create a modal to display success message
    const modalHtml = `
      <div class="modal fade" id="successModal" tabindex="-1" aria-labelledby="successModalLabel" aria-hidden="true">
        <div class="modal-dialog">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title" id="successModalLabel">OPML File Generated!</h5>
              <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
              <p class="text-light">Your OPML file has been downloaded. You can now:</p>
              <ol class="text-light">
                <li>Open your RSS reader</li>
                <li>Look for an option to "Import OPML" or "Import Feeds"</li>
                <li>Select the downloaded file (comiccaster-feeds.opml)</li>
              </ol>
              <p class="text-secondary">Most RSS readers support OPML import. After importing, you can manage each feed individually in your reader.</p>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
            </div>
          </div>
        </div>
      </div>
    `;
    
    // Add the modal to the document
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // Show the modal
    const modal = new bootstrap.Modal(document.getElementById('successModal'));
    modal.show();
    
    // Remove the modal from the DOM when it's closed
    document.getElementById('successModal').addEventListener('hidden.bs.modal', function() {
      this.remove();
    });
  }
}); 