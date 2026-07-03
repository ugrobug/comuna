export const load = async ({ parent, params }) => {
  const parentData = await parent()
  const comun = parentData.comun ?? null

  return {
    comun,
    slug: params.slug,
    template: params.template,
  }
}
