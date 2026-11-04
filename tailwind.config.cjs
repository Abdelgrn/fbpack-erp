/** @type {import('tailwindcss').Config} */
module.exports = {
  // Scanne les templates Django, scripts statiques et classes éventuelles
  // générées depuis le code Python. Les chemins sont relatifs à la racine du projet.
  content: [
    './templates/**/*.html',
    './**/templates/**/*.html',
    './static/**/*.js',
    './**/static/**/*.js',
    './**/*.py',
  ],

  darkMode: 'class',

  theme: {
    extend: {
      colors: {
        neon: '#f3b83a',
        darkbg: '#22375c',
        panel: '#1e293b',
        lightbg: '#f8fafc',
        lightcard: '#ffffff',
      },
    },
  },

  plugins: [],
};
