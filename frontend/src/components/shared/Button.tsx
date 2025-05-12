interface ButtonProps {
  className?: string;
  children: React.ReactNode;
  onClick?: () => void;
  type?: "button" | "submit" | "reset"; // Added type prop
}

export const Button = ({ onClick, children, className = "", type = "button" }: ButtonProps) => {
  return (
    <button
      onClick={onClick}
      type={type} // Pass the type prop to the button
      className={`px-6 py-3 rounded-full outline-none cursor-pointer
                 relative overflow-hidden border border-transparent bg-violet-600 ${className}`}
    >
      {children}
    </button>
  );
};
