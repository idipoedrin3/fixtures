import React from "react";

interface PreviewProps {
  code: string;
  theme?: string;
}

export default function QuickAccessChart({code, theme = "#0CA0F5"}: PreviewProps) {
  return (
    <div className="relative h-full w-full overflow-hidden flex items-center justify-center">
      <div className="w-full h-full cursor-grab active:cursor-grabbing">
        <iframe
          className="size-full transition-opacity duration-300"
          title="Quick Access Diagram"
          srcDoc={`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
  <script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
  <style>
    body {
      margin: 0;
      padding: 0;
      width: 100vw;
      height: 100vh;
      overflow: hidden;
      background-color: transparent;
      font-family: sans-serif;
    }
    #container {
      width: 100vw;
      height: 100vh;
      cursor: grab;
      text-align: center;
      display: flex;
      justify-content: center;
      align-items: center;
    }
    #container:active {
      cursor: grabbing;
    }
    svg {
      width: 100% !important;
      height: 100% !important;
    }
    svg g.node {
      pointer-events: all;
      cursor: pointer;
    }
    .controls {
      position: fixed;
      bottom: 20px;
      right: 20px;
      display: flex;
      flex-direction: column;
      gap: 8px;
      z-index: 1000;
    }
    .btn {
      width: 40px;
      height: 40px;
      border-radius: 8px;
      border: 1px solid #e2e8f0;
      background: white;
      color: #475569;
      font-size: 20px;
      font-weight: bold;
      cursor: pointer;
      display: flex;
      justify-content: center;
      align-items: center;
      box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
      transition: all 0.2s;
      user-select: none;
    }
    .btn:hover {
      background: #f8fafc;
      color: #1e293b;
    }
    .btn:active {
      transform: scale(0.95);
    }
    .btn.active {
      background: ${theme || "#0CA0F5"};
      color: white;
    }
    .search-highlight {
      filter: drop-shadow(0px 0px 10px rgba(59, 130, 246, 0.8)) brightness(1.2);
    }
    @keyframes spin {
      to {
          transform: rotate(360deg);
      }
    }
    .animate-spin {
        animation: spin 1s linear infinite;
        max-width: 45px;
        max-height: 45px;
        margin: 4rem auto;
    }

    #search-input {
      display: none;
      position: fixed;
      bottom: 15px;
      right: 75px;
      
    }
    #search-input input {
      padding: 10px;
      border-radius: 8px;
      border: 1px solid #e2e8f0;
      background: white;
      color: #475569;
      font-size: 20px;
      box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
      transition: all 0.2s;
    }
    #search-input.active {
      display: flex;
      align-items: center;
      gap: 1rem;
    }
  </style>
</head>
<body>
  <div id="container">
    <svg class="animate-spin" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.5" d="M12 3v3m0 12v3m9-9h-3M6 12H3m15.364-6.363l-2.122 2.121m-8.484 8.484l-2.121 2.121m12.727.001l-2.122-2.122M7.758 7.758L5.637 5.637"/></svg>
  </div>
  
  <div class="controls">
    <button class="btn active" id="pan-pitch" title="">
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><g fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"><path d="M14.5 2v2.7m0-2.7c-.45 0-1.53 1.253-1.53 1.253M14.5 2c.451 0 1.53 1.253 1.53 1.253M14.5 11V8.3m0 2.7c.45 0 1.53-1.253 1.53-1.253M14.5 11c-.45 0-1.53-1.253-1.53-1.253M10 6.501h2.7m-2.7 0c0 .449 1.253 1.53 1.253 1.53M10 6.5c0-.451 1.253-1.53 1.253-1.53M19 6.5h-2.7m2.7 0c0-.451-1.253-1.53-1.253-1.53M19 6.5c0 .449-1.253 1.53-1.253 1.53"/><path d="M9.81 3.2c-1.156-.983-1.945-1.423-2.762-1.09c-1.103.449-1.198 1.874-1.376 4.552l-.564 7.724c-.135 1.82-.202 2.73.16 3.188c.249.314.613.513 1.01.553c.577.058 1.3-.493 2.744-1.596c.609-.465.913-.697 1.217-.712c.211-.01.42.047.596.165c.254.17.397.527.683 1.24L13 20.92c.172.427.257.641.394.781a.98.98 0 0 0 .698.299c.195.001.407-.085.831-.258c.424-.172.636-.258.776-.396a1 1 0 0 0 .296-.703c.001-.197-.084-.41-.256-.837l-1.482-3.697c-.286-.713-.43-1.07-.364-1.369a1 1 0 0 1 .314-.536c.23-.202.609-.248 1.367-.34c1.8-.217 2.7-.325 3.075-.772c.258-.306.382-.704.344-1.104c-.032-.35-.29-.71-.786-1.206"/></g></svg>
    </button>
    <button class="btn" id="zoom-in" title="Zoom In">
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="m17 17l4 4m-2-10a8 8 0 1 0-16 0a8 8 0 0 0 16 0M7.5 11h7M11 7.5v7"/></svg>
    </button>
    <button class="btn" id="zoom-out" title="Zoom Out">
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="m17 17l4 4m-2-10a8 8 0 1 0-16 0a8 8 0 0 0 16 0M7.5 11h7"/></svg>
    </button>
    <button class="btn" id="reset" title="Reset">
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M17.5 17.5L22 22m-2-11a9 9 0 0 1-17.064 4M2 11a9 9 0 0 1 17.065-4m0 0V2m0 5H14.5M2.936 15v5m0-5H7.5"/></svg>
    </button>
    <button class="btn" id="search" title="Search">
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="m17 17l4 4m-2-10a8 8 0 1 0-16 0a8 8 0 0 0 16 0"/></svg>
    </button>

    <div id="search-input">
        <button class="btn" id="search-prev" title="Previous">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 6s-6 4.419-6 6s6 6 6 6"/></svg>
        </button>
        <span></span>
        <button class="btn" id="search-next" title="Next">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 6s6 4.419 6 6s-6 6-6 6"/></svg>
        </button>
      <input type="text" placeholder="Search..." />
    </div>
  </div>

  <script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11.12.2/dist/mermaid.esm.min.mjs';
    import elkLayouts from 'https://cdn.jsdelivr.net/npm/@mermaid-js/layout-elk@0.1.9/dist/mermaid-layout-elk.esm.min.mjs';

    mermaid.registerLayoutLoaders(elkLayouts);
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "loose",
      flowchart: {
        htmlLabels: true,
        curve: "basis",
        defaultRenderer: "elk",
      },
    });

    const container = document.getElementById('container');

    let panZoom

    mermaid.render('diagram-svg', \`${code}\`).then(({svg}) => {
      container.innerHTML = svg;
      
      const svgElement = container.querySelector('svg');
      // Remove fixed dimensions to allow scaling
      svgElement.setAttribute('width', '100%');
      svgElement.setAttribute('height', '100%');

      panZoom = svgPanZoom(svgElement, {
        zoomEnabled: true,
        controlIconsEnabled: false,
        fit: true,
        center: true,
        minZoom: 0.1,
        maxZoom: 10,
        mouseWheelZoomEnabled: true,
        pinchEnable: true // Support for touch devices
      });

      // Button listeners
      const panBtn = document.getElementById('pan-pitch')
      panBtn.addEventListener('click', (e) => {
        panBtn.classList.toggle('active');
        if (panZoom.isPanEnabled()) {
          panZoom.disablePan();
        } else {
          panZoom.enablePan();
        }
      });
      document.getElementById('zoom-in').addEventListener('click', () => panZoom.zoomIn());
      document.getElementById('zoom-out').addEventListener('click', () => panZoom.zoomOut());
      document.getElementById('reset').addEventListener('click', () => {
        panZoom.resetZoom();
        panZoom.fit();
        panZoom.center();
      });

      // Handle window resize
      window.addEventListener('resize', () => {
        panZoom.resize();
        panZoom.fit();
        panZoom.center();
      });

      // clickable nodes
      document.querySelectorAll('.node').forEach((node) => {
        node.addEventListener('click', (e) => {
          e.stopPropagation();
          window.parent.postMessage({type: 'NODE_CLICK', payload: node.querySelector('.node-data')?.dataset.node})
        })
        node.addEventListener('mousedown', () => panZoom.disablePan());
        node.addEventListener('mouseup', () => panZoom.enablePan());
      })

    }).catch((err) => {
      container.innerHTML = '<span style="color: red; padding: 20px;">Something went wrong while rendering the diagram.</span>';
    });

       
let search = "", searchResults = [], searchIndex = -1, offset = {x:0, y:0}
let svgWrapperRef = document.querySelector('#container')
let searchBtn = document.querySelector('#search')
let searchInputBox = document.querySelector('#search-input')
let searchInput = document.querySelector('#search-input input')
let searchNum = document.querySelector('#search-input span')
let searchPrev = document.querySelector('#search-prev')
let searchNext = document.querySelector('#search-next')

searchPrev.addEventListener('click', () => {
  searchIndex = (searchIndex - 1 + searchResults.length) % searchResults.length
  updateNum()
  focusElement()
})

searchNext.addEventListener('click', () => {
  searchIndex = (searchIndex + 1) % searchResults.length
  updateNum()
  focusElement()
})
    
const handleSearch = (val) => {
  search = val
    if (!val || !svgWrapperRef) {
      searchResults = []; 
      searchIndex = -1;
      clearHighlights();
      return;
    }

    // Find all nodes and edges
    const elements = Array.from(
      svgWrapperRef.querySelectorAll(".node, .edgePath"),
    )

    const matches = elements.filter((el) =>
      el.textContent?.toLowerCase().includes(val.toLowerCase()),
    );

    searchResults = matches;
    searchIndex = (matches.length > 0 ? 0 : -1);

  updateNum()
  };

    const updateNum = () => {
     searchNum.textContent = searchResults.length > 0 ? \`$\{(searchIndex + 1)} / $\{searchResults.length}\` : "-"
    }

  const clearHighlights = () => {
    svgWrapperRef.querySelectorAll(".search-highlight").forEach((el) => {
      el.classList.remove("search-highlight");
      el.style.filter = "";
    });
  };

  const focusElement = () => {
    const index = searchIndex;
    const el = searchResults[index];
    if (!el || !svgWrapperRef) return;

    clearHighlights();

    // Visual Highlight
    el.classList.add("search-highlight");
    el.style.filter = "drop-shadow(0px 0px 10px rgba(59, 130, 246, 0.8)) brightness(1.2)";

    // Calculate Position
    const containerRect = svgWrapperRef.getBoundingClientRect();
    const elRect = el.getBoundingClientRect();

    // Find the center of the target element
    const elCenterX = elRect.left + elRect.width / 2;
    const elCenterY = elRect.top + elRect.height / 2;

    // Find the center of the container
    const containerCenterX = containerRect.left + containerRect.width / 2;
    const containerCenterY = containerRect.top + containerRect.height / 2;

    // Calculate how much we need to move the wrapper
    const diffX = containerCenterX - elCenterX;
    const diffY = containerCenterY - elCenterY;

    // Update state to shift the view
    offset = {
      x: prev.x + diffX,
      y: prev.y + diffY,
    }

    panZoom?.zoomBy(2.5)
  };

const showSearchInputBox = () => {
  searchInputBox.classList.toggle('active')
}

searchBtn.addEventListener('click', showSearchInputBox)

searchInput.addEventListener('input', e => handleSearch(e.target.value))

</script>
</body>
</html>`}
        />
      </div>
    </div>
  );
}
