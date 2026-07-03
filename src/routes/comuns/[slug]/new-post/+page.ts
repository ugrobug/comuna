export const load = async ({ parent }) => {
  const parentData = await parent()
  return {
    comun: parentData.comun ?? null,
  }
}
