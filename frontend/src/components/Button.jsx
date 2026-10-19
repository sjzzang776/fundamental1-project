// Figma 부품 `Button`: type primary / secondary / danger
export default function Button({ variant = 'primary', size, className = '', children, ...props }) {
  const classes = ['btn', `btn--${variant}`, size && `btn--${size}`, className].filter(Boolean).join(' ')
  return (
    <button type="button" className={classes} {...props}>
      {children}
    </button>
  )
}
