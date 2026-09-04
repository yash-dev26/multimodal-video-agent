const BackgroundAnimation = () => {
  return (
    <div
      className="fixed inset-0 pointer-events-none z-0"
      style={{
        background:
          'radial-gradient(ellipse 80% 50% at 50% -10%, rgba(180, 130, 99, 0.07), transparent 70%), #0c0a09',
      }}
    />
  );
};

export default BackgroundAnimation;
