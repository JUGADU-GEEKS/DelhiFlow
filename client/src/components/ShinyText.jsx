const ShinyText = ({ text, disabled = false, speed = 5, className = '' }) => {
  const animationDuration = `${speed}s`;

  return (
    <div className={`inline-block relative ${className}`}>
      {/* Base gradient text */}
      <span className="text-transparent bg-clip-text bg-gradient-to-r from-purple-300 via-fuchsia-200 to-pink-700">
        {text}
      </span>
      
      {/* Shiny overlay */}
      {!disabled && (
        <span 
          className="absolute inset-0 text-transparent"
          style={{
            background: 'linear-gradient(120deg, rgba(255, 255, 255, 0) 40%, rgba(255, 255, 255, 0.8) 50%, rgba(255, 255, 255, 0) 60%)',
            backgroundSize: '200% 100%',
            WebkitBackgroundClip: 'text',
            backgroundClip: 'text',
            animation: `shine ${animationDuration} linear infinite`,
          }}
        >
          {text}
        </span>
      )}
      
      <style>{`
        @keyframes shine {
          0% { background-position: 100% 0; }
          100% { background-position: -100% 0; }
        }
      `}</style>
    </div>
  );
};

export default ShinyText;

// tailwind.config.js
// module.exports = {
//   theme: {
//     extend: {
//       keyframes: {
//         shine: {
//           '0%': { 'background-position': '100%' },
//           '100%': { 'background-position': '-100%' },
//         },
//       },
//       animation: {
//         shine: 'shine 5s linear infinite',
//       },
//     },
//   },
//   plugins: [],
// };
