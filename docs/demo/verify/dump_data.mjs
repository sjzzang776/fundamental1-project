import { MENUS, OPTIONS, OPTION_ALIASES } from '../data.js'
console.log(JSON.stringify({ menus: MENUS.map(({ id, name, aliases }) => ({ id, name, aliases })), options: OPTIONS.map(({ id, name, groupId }) => ({ id, name, option_group_id: groupId })), aliases: OPTION_ALIASES }))
