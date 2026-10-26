
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname);

const IGNORAR = new Set([
    "node_modules",
    ".git",
    ".next",
    "dist",
    "build",
    "coverage",
    ".venv",
    "venv"
]);

const ARCHIVOS_CLAVE = new Set([
    "package.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "package-lock.json",
    "vite.config.js",
    "vite.config.ts",
    "next.config.js",
    "next.config.ts",
    "tsconfig.json",
    "pyproject.toml",
    "requirements.txt",
    "Cargo.toml",
    "go.mod",
    "Dockerfile",
    ".env.example",
    "README.md"
]);

const carpetas = new Set();
const archivosClave = [];
let totalArchivos = 0;
let totalCarpetas = 0;

function escanear(dir, nivel = 0) {
    let entradas;

    try {
        entradas = fs.readdirSync(dir, {
            withFileTypes: true
        });
    } catch (error) {
        console.log("SIN ACCESO:", dir);
        return;
    }

    entradas.sort((a, b) =>
        a.name.localeCompare(b.name)
    );

    for (const entrada of entradas) {
        const nombre = entrada.name;
        const ruta = path.join(dir, nombre);
        const relativa = path.relative(ROOT, ruta);

        if (entrada.isDirectory()) {
            if (IGNORAR.has(nombre)) continue;

            totalCarpetas++;
            carpetas.add(nombre);

            console.log("  ".repeat(nivel) + "📁 " + nombre + "/");

            if (nivel < 5) {
                escanear(ruta, nivel + 1);
            } else {
                console.log(
                    "  ".repeat(nivel + 1) + "...nivel máximo"
                );
            }
        } else if (entrada.isFile()) {
            totalArchivos++;

            if (
                ARCHIVOS_CLAVE.has(nombre) ||
                nombre.endsWith(".env")
            ) {
                archivosClave.push(relativa);
                console.log(
                    "  ".repeat(nivel) + "📄 " + nombre
                );
            }
        }
    }
}

console.log("\n=== TRIAD STUDIO: ESCANEO ===");
console.log("Ruta:", ROOT, "\n");

escanear(ROOT);

console.log("\n=== RESUMEN ===");
console.log("Carpetas:", totalCarpetas);
console.log("Archivos:", totalArchivos);
console.log("\n=== CARPETAS PRINCIPALES ===");

for (const nombre of [
    "workspace",
    "front",
    "back"
]) {
    console.log(
        `${carpetas.has(nombre) ? "ENCONTRADA" : "NO ENCONTRADA"}: ${nombre}`
    );
}

console.log("\n=== ARCHIVOS DE CONFIGURACIÓN ===");

for (const archivo of archivosClave) {
    console.log(archivo);
}

console.log("\nEscaneo terminado.");
