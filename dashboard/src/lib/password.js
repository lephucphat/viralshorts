// 0 = too short to submit (the server's minimum is 8); 1-3 = how much beyond
// the minimum it goes. A hint for the person, never a substitute for the
// server's own check.
export function passwordStrength(pw) {
  if (pw.length < 8) return 0;
  let score = 1;
  if (pw.length >= 12) score += 1;
  if (/[a-zA-Z]/.test(pw) && /\d/.test(pw) && /[^a-zA-Z0-9]/.test(pw)) score += 1;
  else if (pw.length >= 10 && /[a-zA-Z]/.test(pw) && /\d/.test(pw)) score += 1;
  return Math.min(3, score);
}
