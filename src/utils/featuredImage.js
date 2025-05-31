import fs from "fs";
const pool = fs.readdirSync("./public/featured");
export function pickImage(slug) {
  let hash = 0;
  for (const c of slug) hash = (hash * 31 + c.charCodeAt(0)) % pool.length;
  return `/featured/${pool[hash]}`;
}
