const API_BASE = "";

let currentCategoriaFilter = "";

document.addEventListener("DOMContentLoaded", function () {
    cargarStats();
    cargarPersonas();

    const uploadArea = document.getElementById("uploadArea");
    const fileInput = document.getElementById("fileInput");

    uploadArea.addEventListener("click", function () {
        fileInput.click();
    });

    uploadArea.addEventListener("dragover", function (e) {
        e.preventDefault();
        uploadArea.classList.add("dragover");
    });

    uploadArea.addEventListener("dragleave", function () {
        uploadArea.classList.remove("dragover");
    });

    uploadArea.addEventListener("drop", function (e) {
        e.preventDefault();
        uploadArea.classList.remove("dragover");
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            subirArchivos(files);
        }
    });

    fileInput.addEventListener("change", function () {
        if (this.files.length > 0) {
            subirArchivos(this.files);
        }
    });

    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") {
            cerrarModal();
        }
    });
});

async function cargarStats() {
    try {
        const res = await fetch(`${API_BASE}/api/stats`);
        const data = await res.json();
        document.getElementById("stat-total").textContent = data.total;
        document.getElementById("stat-vivos").textContent = data.vivos;
        document.getElementById("stat-desaparecidos").textContent = data.desaparecidos;
        document.getElementById("stat-fallecidos").textContent = data.fallecidos;
    } catch (err) {
        console.error("Error cargando stats:", err);
    }
}

async function cargarPersonas() {
    const q = document.getElementById("searchInput").value.trim();
    const categoria = currentCategoriaFilter || document.getElementById("categoriaFilter").value;
    let url = `${API_BASE}/api/personas?`;

    if (q) url += `q=${encodeURIComponent(q)}&`;
    if (categoria) url += `categoria=${encodeURIComponent(categoria)}`;

    try {
        const res = await fetch(url);
        const data = await res.json();
        renderPersonas(data);
    } catch (err) {
        console.error("Error cargando personas:", err);
    }
}

function buscarPersonas() {
    cargarPersonas();
}

function filtrarCategoria(categoria) {
    currentCategoriaFilter = categoria;
    document.getElementById("categoriaFilter").value = categoria;
    cargarPersonas();
}

function renderPersonas(personas) {
    const tbody = document.getElementById("resultsBody");
    const noResults = document.getElementById("noResults");
    const resultsCount = document.getElementById("results-count");

    resultsCount.classList.remove("hidden");
    resultsCount.textContent = `${personas.length} resultado(s) encontrado(s)`;

    if (personas.length === 0) {
        tbody.innerHTML = "";
        noResults.classList.remove("hidden");
        return;
    }

    noResults.classList.add("hidden");
    tbody.innerHTML = personas.map(p => {
        const categoriaLabel = {
            "vivo_sitio_actual": "Vivo / Sitio Actual",
            "desaparecido": "Desaparecido",
            "fallecido": "Fallecido"
        }[p.categoria] || p.categoria;

        const categoriaClass = {
            "vivo_sitio_actual": "categoria-vivo",
            "desaparecido": "categoria-desaparecido",
            "fallecido": "categoria-fallecido"
        }[p.categoria] || "";

        const fecha = p.fecha_registro ? new Date(p.fecha_registro).toLocaleDateString("es-VE") : "-";

        return `<tr>
            <td>${p.cedula || "-"}</td>
            <td><strong>${p.nombre_completo}</strong></td>
            <td><span class="categoria-badge ${categoriaClass}">${categoriaLabel}</span></td>
            <td>${p.fuente_documento || "-"}</td>
            <td>${fecha}</td>
            <td class="acciones-cell">
                <button class="btn btn-small btn-edit" onclick="abrirModal(${p.id}, '${p.nombre_completo.replace(/'/g, "\\'")}', '${p.cedula || ""}', '${p.categoria}')">Editar</button>
                <button class="btn btn-small btn-delete" onclick="eliminarPersona(${p.id})">Eliminar</button>
            </td>
        </tr>`;
    }).join("");
}

async function subirArchivos(files) {
    const progress = document.getElementById("uploadProgress");
    const progressFill = document.getElementById("progressFill");
    const uploadStatus = document.getElementById("uploadStatus");
    const uploadResult = document.getElementById("uploadResult");

    progress.classList.remove("hidden");
    uploadResult.classList.add("hidden");
    progressFill.style.width = "0%";
    uploadStatus.textContent = "Subiendo archivos...";

    const formData = new FormData();
    for (const file of files) {
        formData.append("files", file);
    }

    progressFill.style.width = "30%";
    uploadStatus.textContent = "Procesando documentos...";

    try {
        const res = await fetch(`${API_BASE}/api/upload`, {
            method: "POST",
            body: formData
        });

        progressFill.style.width = "100%";
        const data = await res.json();

        if (!res.ok) {
            uploadResult.className = "alert-error";
            uploadResult.textContent = data.detail || "Error al procesar archivos";
        } else {
            uploadResult.className = "alert-success";
            uploadResult.textContent = data.message;
        }

        uploadResult.classList.remove("hidden");
        cargarStats();
        cargarPersonas();
    } catch (err) {
        uploadResult.className = "alert-error";
        uploadResult.textContent = "Error de conexión al servidor";
        uploadResult.classList.remove("hidden");
    }

    setTimeout(() => {
        progress.classList.add("hidden");
    }, 2000);
}

async function sincronizarDrive() {
    const folderName = document.getElementById("driveFolderName").value.trim() || "DashboardPersonas";
    const driveResult = document.getElementById("driveResult");

    driveResult.className = "alert-success";
    driveResult.textContent = "Sincronizando con Google Drive...";
    driveResult.classList.remove("hidden");

    try {
        const res = await fetch(`${API_BASE}/api/drive/sync?carpeta_raiz=${encodeURIComponent(folderName)}`, {
            method: "POST"
        });
        const data = await res.json();

        if (!res.ok) {
            driveResult.className = "alert-error";
            driveResult.textContent = data.detail || "Error de sincronización";
        } else {
            driveResult.className = "alert-success";
            driveResult.textContent = data.message;
        }

        cargarStats();
        cargarPersonas();
    } catch (err) {
        driveResult.className = "alert-error";
        driveResult.textContent = "Error de conexión al servidor. Verifica que el backend esté corriendo.";
    }
}

async function exportarDatos() {
    try {
        const res = await fetch(`${API_BASE}/api/export`);
        const data = await res.json();

        const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "personas_export.json";
        a.click();
        URL.revokeObjectURL(url);
    } catch (err) {
        console.error("Error exportando:", err);
    }
}

function abrirModal(id, nombre, cedula, categoria) {
    document.getElementById("editId").value = id;
    document.getElementById("editNombre").value = nombre;
    document.getElementById("editCedula").value = cedula;
    document.getElementById("editCategoria").value = categoria;
    document.getElementById("editModal").classList.remove("hidden");
}

function cerrarModal() {
    document.getElementById("editModal").classList.add("hidden");
}

async function guardarEdicion() {
    const id = document.getElementById("editId").value;
    const nombre = document.getElementById("editNombre").value.trim();
    const cedula = document.getElementById("editCedula").value.trim();
    const categoria = document.getElementById("editCategoria").value;

    if (!nombre) {
        alert("El nombre es obligatorio.");
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/api/personas/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                nombre_completo: nombre,
                cedula: cedula || null,
                categoria: categoria
            })
        });

        if (!res.ok) {
            const err = await res.json();
            alert(err.detail || "Error al actualizar");
            return;
        }

        cerrarModal();
        cargarStats();
        cargarPersonas();
    } catch (err) {
        alert("Error de conexión");
    }
}

async function eliminarPersona(id) {
    if (!confirm("¿Estás seguro de eliminar esta persona?")) return;

    try {
        const res = await fetch(`${API_BASE}/api/personas/${id}`, { method: "DELETE" });
        if (!res.ok) {
            alert("Error al eliminar");
            return;
        }
        cargarStats();
        cargarPersonas();
    } catch (err) {
        alert("Error de conexión");
    }
}
