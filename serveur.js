const express = require('express');
const multer = require('multer');
const AdmZip = require('adm-zip');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');

const app = express();
const PORT = process.env.PORT || 3000;

// Dossier temporaire pour stocker les prévisualisations extraites
const TEMP_DIR = path.join(__dirname, 'temp_previews');
if (!fs.existsSync(TEMP_DIR)) {
    fs.mkdirSync(TEMP_DIR, { recursive: true });
}

// Configuration de Multer pour recevoir les ZIP en mémoire
const upload = multer({
    storage: multer.memoryStorage(),
    limits: { fileSize: 50 * 1024 * 1024 }, // Limite de 50 Mo par ZIP
    fileFilter: (req, file, cb) => {
        if (file.mimetype === 'application/zip' || file.originalname.endsWith('.zip')) {
            cb(null, true);
        } else {
            cb(new Error('Seuls les fichiers ZIP sont autorisés.'));
        }
    }
});

// Middleware d'authentification par jeton temporaire pour APK Studio
const verifyToken = (req, res, next) => {
    const token = req.headers['x-preview-token'] || req.query.token;
    const expectedToken = process.env.PREVIEW_SECRET_TOKEN;

    if (expectedToken && token !== expectedToken) {
        return res.status(403.json({ error: 'Accès non autorisé : jeton invalide ou manquant.' }));
    }
    next();
};

// Route d'upload et de décompression du ZIP
app.post('/api/upload-preview', verifyToken, upload.single('zipFile'), (req, res) => {
    try {
        if (!req.file) {
            return res.status(400).json({ error: 'Aucun fichier ZIP fourni.' });
        }

        const projectId = crypto.randomBytes(16).toString('hex');
        const projectDir = path.join(TEMP_DIR, projectId);
        fs.mkdirSync(projectDir, { recursive: true });

        // Décompression du ZIP en mémoire
        const zip = new AdmZip(req.file.buffer);
        zip.extractAllTo(projectDir, true);

        // Recherche d'un index.html à la racine ou dans le premier sous-dossier
        let entryPoint = 'index.html';
        if (!fs.existsSync(path.join(projectDir, 'index.html'))) {
            const files = fs.readdirSync(projectDir);
            const subDir = files.find(f => fs.statSync(path.join(projectDir, f)).isDirectory());
            if (subDir && fs.existsSync(path.join(projectDir, subDir, 'index.html'))) {
                entryPoint = `${subDir}/index.html`;
            }
        }

        const previewUrl = `/preview/${projectId}/${entryPoint}`;

        // Planification de la suppression automatique après 2 heures
        setTimeout(() => {
            if (fs.existsSync(projectDir)) {
                fs.rmSync(projectDir, { recursive: true, force: true });
            }
        }, 2 * 60 * 60 * 1000);

        res.json({
            success: true,
            projectId: projectId,
            previewUrl: previewUrl
        });

    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Erreur lors du traitement du fichier ZIP.' });
    }
});

// Route pour servir les fichiers extraits du site temporaire
app.use('/preview/:projectId', (req, res, next) => {
    const { projectId } = req.params;
    const projectPath = path.join(TEMP_DIR, projectId);

    if (!fs.existsSync(projectPath)) {
        return res.status(404).send('Aperçu expiré ou introuvable.');
    }

    express.static(projectPath)(req, res, next);
});

// Route de suppression manuelle d'un projet
delete
app.delete('/api/preview/:projectId', verifyToken, (req, res) => {
    const { projectId } = req.params;
    const projectPath = path.join(TEMP_DIR, projectId);

    if (fs.existsSync(projectPath)) {
        fs.rmSync(projectPath, { recursive: true, force: true });
        return res.json({ success: true, message: 'Projet supprimé.' });
    }
    res.status(404).json({ error: 'Projet introuvable.' });
});

app.listen(PORT, () => {
    console.log(`Serveur APK Studio démarré sur le port ${PORT}`);
});
