const BackgroundAnimation = () => {
  return (
    <div
      className="fixed inset-0 pointer-events-none z-0"
      style={{
        background:
          'radial-gradient(ellipse 70% 45% at 50% -8%, rgba(201, 162, 78, 0.09), transparent 65%), ' +
          'radial-gradient(ellipse 60% 40% at 100% 100%, rgba(169, 132, 58, 0.05), transparent 70%), ' +
          '#08080A',
      }}
    />
  );
};

export default BackgroundAnimation;
